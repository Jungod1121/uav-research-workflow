#!/usr/bin/env bash
# run_mission.sh — 执行方框任务 + 同步录制 rosbag2（时间对齐由同一脚本保证）
# 用法: run_mission.sh <mission> <exp_id> [key=value ...]
#   mission 目前支持: square ; key=value 覆盖: side=4.0 height=2.5 speed=1.5 wp_tol=0.35
set -euo pipefail

WF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MISSION="${1:?usage: run_mission.sh <mission> <exp_id> [k=v ...]}"; shift
EXP_ID="${1:?missing exp_id}"; shift || true

[ "$MISSION" = "square" ] || { echo "ERROR: unknown mission '$MISSION' (only square)"; exit 1; }

EXP_DIR="$WF_DIR/experiments/$EXP_ID"
mkdir -p "$EXP_DIR"/{bags,views,logs}
METRICS="$EXP_DIR/metrics.json"


# ---- 参数解析（Hydra 风格 k=v，缺省值在此钉死）----
SIDE=4.0 HEIGHT=2.5 SPEED=1.5 WP_TOL=0.35 DUR=600 VIEW_EVERY=5
for kv in "$@"; do
  case "$kv" in
    side=*) SIDE="${kv#side=}" ;; height=*) HEIGHT="${kv#height=}" ;;
    speed=*) SPEED="${kv#speed=}" ;; wp_tol=*) WP_TOL="${kv#wp_tol=}" ;;
    dur=*) DUR="${kv#dur=}" ;; view_every=*) VIEW_EVERY="${kv#view_every=}" ;;
    *) echo "WARN: unknown override '$kv' ignored" ;;
  esac
done
echo "[mission] config: side=$SIDE height=$HEIGHT speed=$SPEED wp_tol=$WP_TOL view_every=$VIEW_EVERY"

# ---- 血缘 metadata（P1: proposal/gap-cell/hypothesis/parent 经 env 传入, 缺省 null）----
python3 "$WF_DIR/scripts/exp_metadata.py" write "$EXP_DIR" "$MISSION" \
  ${PROPOSAL_ID:+--proposal "$PROPOSAL_ID"} \
  ${GAP_CELL_ID:+--gap-cell "$GAP_CELL_ID"} \
  ${HYPOTHESIS:+--hypothesis "$HYPOTHESIS"} \
  ${PARENT_EXP:+--parent "$PARENT_EXP"} ${ITER_ROUND:+--round "$ITER_ROUND"} \
  --config "side=$SIDE" "height=$HEIGHT" "speed=$SPEED" "wp_tol=$WP_TOL" "dur=$DUR" "view_every=$VIEW_EVERY"

set +u   # ROS setup.bash 不兼容 nounset
source /opt/ros/humble/setup.bash
[ -f "$HOME/px4_ros2_ws/install/setup.bash" ] && source "$HOME/px4_ros2_ws/install/setup.bash"
set -u
export ROS_DOMAIN_ID=77

# ---- 1. 启动 rosbag 录制（关键 fmu 话题 + tf）----
TOPICS="/fmu/out/vehicle_local_position /fmu/out/vehicle_attitude /fmu/out/vehicle_odometry \
/fmu/out/vehicle_control_mode /fmu/out/vehicle_status_v1 \
/fmu/out/sensor_combined"
ros2 bag record -o "$EXP_DIR/bags/flight" $TOPICS \
  >"$EXP_DIR/logs/bag.log" 2>&1 &   # Humble 无 mcap 插件, 用默认 sqlite3
BAG_PID=$!
sleep 2

# ---- 2. 视觉采样循环（后台；无 DISPLAY 则跳过并记录）----
(
  if [ -n "${DISPLAY:-}" ]; then
    i=0
    while kill -0 $BAG_PID 2>/dev/null && [ $i -lt $((DUR / VIEW_EVERY)) ]; do
      sleep "$VIEW_EVERY"; i=$((i+1))
      ts=$(date +%H%M%S)
      import -window root "$EXP_DIR/views/view_${ts}.png" 2>/dev/null \
        || echo "capture failed at ${ts}" >>"$EXP_DIR/logs/views.log"
    done
  else
    echo "NO_DISPLAY: 视觉通道未采集（可用 Xvfb 或加 --headless GUI）" >"$EXP_DIR/logs/views.log"
  fi
) &
VIEW_PID=$!

# ---- 3. 执行任务 ----
set +e
python3 "$WF_DIR/scripts/square_offboard.py" "$SIDE" "$HEIGHT" "$SPEED" "$WP_TOL" "$METRICS" \
  2>&1 | tee "$EXP_DIR/logs/mission.log"
RC=${PIPESTATUS[0]}
set -e

# ---- 4. 收尾：停录制、停视觉 ----
kill $BAG_PID 2>/dev/null || true
kill $VIEW_PID 2>/dev/null || true
sleep 3
pkill -INT -f "ros2 bag record" 2>/dev/null || true

if [ $RC -eq 0 ] && grep -qE "MISSION_(DONE|PARTIAL)" "$EXP_DIR/logs/mission.log"; then
  grep -oE "MISSION_(DONE|PARTIAL) .*" "$EXP_DIR/logs/mission.log" | tail -1
else
  echo "MISSION_FAILED rc=$RC — 见 $EXP_DIR/logs/"
fi
exit 0   # 任务失败不阻断外层流程，交给 analyze-results 判断
