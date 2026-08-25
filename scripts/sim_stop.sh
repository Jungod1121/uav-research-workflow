#!/usr/bin/env bash
# sim_stop.sh — 干净关停整个仿真栈（PX4/Gazebo/uXRCE/RViz/offboard/rosbag）
# 设计参考用户 run-slam 的教训：残余 Python/仿真进程会污染下一次实验。
set -u

DOMAIN_PIDS=""

kill_tree() {
  local pid="$1"
  pkill -TERM -P "$pid" 2>/dev/null
  kill -TERM "$pid" 2>/dev/null
}

echo "[sim_stop] stopping stack components..."

# 1. 优雅：先停录制与任务节点
for pat in "ros2 bag record" "square_offboard" "offboard_control"; do
  pkill -TERM -f "$pat" 2>/dev/null && echo "  sent TERM -> $pat"
done
sleep 2

# 2. 栈组件（TERM 再 KILL）
for name in MicroXRCEAgent rviz2; do
  pkill -TERM -x "$name" 2>/dev/null && echo "  sent TERM -> $name"
done
pkill -TERM -f "gz sim" 2>/dev/null && echo "  sent TERM -> gz sim"
pkill -TERM -f "px4-rc|bin/px4" 2>/dev/null && echo "  sent TERM -> px4"
sleep 3

# 3. 兜底 KILL
for pat in "MicroXRCEAgent" "gz sim" "ruby.*gz" "bin/px4" "rviz2" "ros2 bag record"; do
  pgrep -f "$pat" >/dev/null 2>&1 && { pkill -KILL -f "$pat"; echo "  KILLed stubborn -> $pat"; }
done

# 4. 验证干净
sleep 1
LEFT=$(pgrep -af "MicroXRCEAgent|gz sim|bin/px4|rviz2|ros2 bag record" || true)
if [ -z "${LEFT}" ]; then
  echo "[sim_stop] CLEAN_SHUTDOWN"
  exit 0
else
  echo "[sim_stop] WARN residual processes:"
  echo "$LEFT"
  exit 1
fi
