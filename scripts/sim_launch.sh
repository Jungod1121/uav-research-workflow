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
if [ "$HEADLESS" = "1" ]; then LAUNCH_ENV+=(HEADLESS=1); fi
# 必须用 make 协调启动(它负责 gz server+px4+lockstep 握手的时序)。
# 手动分离启动会破坏 lockstep: 世界被桥接暂停后传感器系统不激活。
# stdin 必须保持打开: EOF 会让 px4 shell 疯狂刷提示符(10GB级日志), 用 tail -f 喂住
( cd "$PX4_DIR" && env "${LAUNCH_ENV[@]}" tail -f /dev/null | \
    make px4_sitl gz_x500 >"$LOG_DIR/px4.log" 2>&1 & )

# ---- 3. RViz（可选）----------------------------------------------------
if [ "$RVIZ" = "1" ]; then
  if [ -n "${DISPLAY:-}" ]; then
    (sleep 8 && rviz2 ${RVIZ_CFG:+-d "$RVIZ_CFG"} >"$LOG_DIR/rviz.log" 2>&1 &)
    echo "[launch] rviz2 queued (DISPLAY=$DISPLAY)"
  else
    echo "[launch] WARN: no DISPLAY, skipping rviz2 (截图通道将不可用，可用 Xvfb 替代)"
  fi
fi

# ---- 4. READY 探测：等 /fmu/out 话题出现 -------------------------------
echo "[launch] waiting for READY (px4 <-> agent <-> ROS2)..."
READY=0
for i in $(seq 1 120); do   # 最长 ~4 分钟（ros2 CLI 每轮约 1-2s）
  if ros2 topic list 2>/dev/null | grep -q "^/fmu/out/"; then
    READY=1; break
  fi
  sleep 1
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
