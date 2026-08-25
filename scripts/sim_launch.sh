#!/usr/bin/env bash
# sim_launch.sh — 幂等启动仿真栈: 环境清理 -> uXRCE Agent -> PX4 SITL(Gazebo Harmonic) [-> RViz]
# 用法:
#   ./sim_launch.sh            # 带 GUI (gz client + rviz2)
#   ./sim_launch.sh --headless # 无 gz GUI（rviz2 仍启动，供截图/观察）
#   ./sim_launch.sh --no-rviz  # 完全无窗口（纯数据采集）
set -euo pipefail

WF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${WF_DIR}/experiments/.live"
mkdir -p "$LOG_DIR"

HEADLESS=0; RVIZ=1
for arg in "$@"; do
  case "$arg" in
    --headless) HEADLESS=1 ;;
    --no-rviz)  RVIZ=0 ;;
  esac
done

export ROS_DOMAIN_ID=77          # 本工作流固定域，避免 DDS 串台
export GZ_VERSION=harmonic       # ros_gz / 工具链提示

# GL 自愈: NVIDIA 驱动/库版本不匹配(unattended-upgrades 后未重启的典型症状)时
# GLX 应用(rviz2/gz GUI)会崩。检测到则强制 GLX 走 Mesa 软渲染兜底(根治=重启机器)。
# 注意用 /proc/modules 而非 lsmod(setsid 环境 PATH 可能无 sbin)
if ! nvidia-smi >/dev/null 2>&1 && grep -q "^nvidia" /proc/modules 2>/dev/null; then
  export __GLX_VENDOR_LIBRARY_NAME=mesa LIBGL_ALWAYS_SOFTWARE=1
  echo "[launch] NVIDIA 驱动不匹配 -> GLX 回退 Mesa 软渲染 (根治请重启)"
fi

echo "[launch] pre-clean check..."
"$WF_DIR/scripts/sim_stop.sh" >/dev/null 2>&1 || true

set +u   # ROS setup.bash 不兼容 nounset
source /opt/ros/humble/setup.bash
[ -f "$HOME/px4_ros2_ws/install/setup.bash" ] && source "$HOME/px4_ros2_ws/install/setup.bash"
set -u
unset GZ_SIM_RESOURCE_PATH SDF_PATH || true   # 防 ArduPilot 等环境残留（见 experiment-setup 坑表）
export PX4_GZ_NO_FOLLOW=1                     # 关闭默认跟随相机（坑清单#1）

# ---- 1. uXRCE-DDS Agent -------------------------------------------------
# 优先用静态链接的本地构建（/usr/local 的副本可能缺 .so，见 experiment-setup 坑表）
AGENT_BIN="$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent"
[ -x "$AGENT_BIN" ] || AGENT_BIN="$(command -v MicroXRCEAgent || true)"
[ -n "$AGENT_BIN" ] || { echo "ERROR: MicroXRCEAgent 未找到"; exit 1; }

if ! pgrep -x MicroXRCEAgent >/dev/null; then
  ("$AGENT_BIN" udp4 -p 8888 >"$LOG_DIR/xrce.log" 2>&1 &)
  echo "[launch] MicroXRCEAgent starting (udp4:8888) [$AGENT_BIN]"
else
  echo "[launch] MicroXRCEAgent already running"
fi

# ---- 2. PX4 SITL + Gazebo ----------------------------------------------
PX4_DIR="$HOME/PX4-Autopilot"
[ -d "$PX4_DIR" ] || { echo "ERROR: $PX4_DIR not found — 先执行 provision.sh 或见 experiment-setup skill"; exit 1; }

LAUNCH_ENV=()
# server 恒 HEADLESS: `gz sim -r`(server+GUI 同进程) 在 GLX 异常时会连 server 一起带崩。
# GUI 客户端在 READY 后分离启动(带 GL 兜底 env), 崩了也不影响仿真。
( cd "$PX4_DIR" && env HEADLESS=1 "${LAUNCH_ENV[@]}" tail -f /dev/null | \
    make px4_sitl gz_x500 >"$LOG_DIR/px4.log" 2>&1 & )

# ---- 3. GUI 客户端（可选, READY 后分离启动, 崩溃不影响仿真）----------------
if [ "$RVIZ" = "1" ] && [ -n "${DISPLAY:-}" ]; then
  (sleep 10 && rviz2 ${RVIZ_CFG:+-d "$RVIZ_CFG"} >"$LOG_DIR/rviz.log" 2>&1 &)
  echo "[launch] rviz2 queued (DISPLAY=$DISPLAY)"
else
  [ "$RVIZ" = "1" ] && echo "[launch] WARN: no DISPLAY, skip rviz2"
fi
if [ "$HEADLESS" != "1" ] && [ -n "${DISPLAY:-}" ]; then
  (sleep 14 && gz sim -g -v 0 >"$LOG_DIR/gzgui.log" 2>&1 &)
  echo "[launch] gz GUI client queued"
fi

# ---- 4. READY 探测：等 /fmu/out 话题出现 -------------------------------
# 坑: ros2 CLI daemon 缓存启动时的 ROS_DOMAIN_ID, 域变更后永远发现不了话题 → 探针死等。
# 探测前强制重启 daemon, 且每次调用加 timeout 防挂死。
ATTEMPTS=0
while [ $ATTEMPTS -lt 3 ]; do
  ATTEMPTS=$((ATTEMPTS+1))
  [ $ATTEMPTS -gt 1 ] && { echo "[launch] 第 $ATTEMPTS 次尝试(数据流未通,整栈重启)"; ./scripts/sim_stop.sh >/dev/null 2>&1; sleep 3
    ( cd "$PX4_DIR" && env HEADLESS=1 tail -f /dev/null | make px4_sitl gz_x500 >"$LOG_DIR/px4.log" 2>&1 & ); }
  ros2 daemon stop >/dev/null 2>&1 || true
  READY=0
  for i in $(seq 1 40); do
    if timeout 12 ros2 topic hz /fmu/out/sensor_combined --window 5 2>/dev/null | grep -q "min"; then
      READY=1; break
    fi
    sleep 1
  done
  [ "$READY" = "1" ] && break
done
if [ "$READY" = "1" ]; then
  echo "[launch] READY — /fmu topics visible ( waited ${i}s )"
  echo "[launch] logs: $LOG_DIR/{px4,xrce,rviz}.log"
  exit 0
else
  echo "[launch] TIMEOUT — last px4.log lines:"
  tail -50 "$LOG_DIR/px4.log" || true
  "$WF_DIR/scripts/sim_stop.sh" || true
  exit 1
fi
