#!/usr/bin/env bash
# smoke_test.sh — 环境哨兵: 栈起停+数据流+MCP 握手+GLX 状态一条龙。全绿输出 SMOKE_OK
set -u; FAIL=0
ck(){ eval "$2" >/dev/null 2>&1 && echo "  OK  $1" || { echo "  FAIL $1"; FAIL=1; }; }
echo "[smoke] 静态环境"
ck "ROS2 Humble"        "ls /opt/ros/humble/setup.bash"
ck "px4_ros2_ws"        "ls ~/px4_ros2_ws/install/setup.bash"
ck "Gazebo Harmonic"    "gz sim --versions"
ck "PX4 binary"         "ls ~/PX4-Autopilot/build/px4_sitl_default/bin/px4"
ck "uXRCE Agent"        "test -x ~/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent"
ck "磁盘>10G"           "bash -c '[ \$(df --output=avail -B1 ~ | tail -1) -gt 10737418240 ]'"
echo "[smoke] MCP 握手"
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"s","version":"0"}}}' > /tmp/mcp_init.json
ck "mcp-rosbags"        "cat /tmp/mcp_init.json | MCP_ROSBAG_DIR=/tmp PYTHONPATH=$HOME/ai-skills/mcp-rosbags/src timeout 8 $HOME/ai-skills/mcp-rosbags/venv/bin/python $HOME/ai-skills/mcp-rosbags/src/server.py 2>/dev/null | grep -q serverInfo"
ck "ros-mcp"            "cat /tmp/mcp_init.json | bash -c 'source /opt/ros/humble/setup.bash; ROS_DOMAIN_ID=77 timeout 8 $HOME/ai-skills/ros-mcp/venv/bin/python $HOME/ai-skills/ros-mcp/ros-general.py 2>/dev/null' | grep -q serverInfo"
echo "[smoke] 栈起停+数据流"
cd "$(dirname "$0")/.."
timeout 150 ./scripts/sim_launch.sh --headless >/dev/null 2>&1 && \
ck "READY+数据流" "bash -c 'source /opt/ros/humble/setup.bash; source ~/px4_ros2_ws/install/setup.bash; export ROS_DOMAIN_ID=77; timeout 10 ros2 topic hz /fmu/out/sensor_combined --window 10 2>&1 | grep -q \"min\"'" || { echo "  FAIL 栈启动"; FAIL=1; }
./scripts/sim_stop.sh >/dev/null 2>&1
[ $FAIL -eq 0 ] && echo "SMOKE_OK" || echo "SMOKE_FAILED"
exit $FAIL
