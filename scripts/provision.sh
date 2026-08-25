#!/usr/bin/env bash
# provision.sh — 一条命令装齐科研工作流（幂等：已装的部分自动跳过）
# 覆盖: workflow 仓库 skills 链接 / MCP servers / Gazebo Harmonic + PX4 v1.16 + uXRCE + px4_ros2_ws
# 用法: ./provision.sh [--skip-px4]   # --skip-px4 只装轻量部分(约5分钟)
set -euo pipefail

WF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_PX4=0; [[ "${1:-}" == "--skip-px4" ]] && SKIP_PX4=1
step(){ echo -e "\n\033[1;34m[provision]\033[0m $*"; }

step "0/7 系统依赖检查"
for c in git python3 curl; do command -v $c >/dev/null || { echo "缺少 $c"; exit 1; }; done
source /opt/ros/humble/setup.bash 2>/dev/null || { echo "需要 ROS2 Humble (/opt/ros/humble)"; exit 1; }

step "1/7 skills -> ~/.claude/skills/"
mkdir -p ~/.claude/skills
for d in "$WF"/skills/*/; do
  name=$(basename "$d")
  ln -sfn "$d" ~/.claude/skills/"$name"
done
ls ~/.claude/skills/ | sed 's/^/  - /'

step "2/7 脚本可执行权限"
chmod +x "$WF"/scripts/*.sh "$WF"/scripts/*.py

step "3/7 Python 工具依赖（观察包/bag 解析）"
python3 -m pip install --quiet --user rosbags matplotlib pyyaml 2>/dev/null \
  || echo "  WARN: pip 安装失败，obs_pack 的轨迹图功能降级"

step "4/7 systemd timer（gap-watch 每日追踪，可选）"
mkdir -p ~/.config/systemd/user
cp "$WF/scripts/systemd/uav-gap-watch."{service,timer} ~/.config/systemd/user/ 2>/dev/null \
  && systemctl --user daemon-reload \
  && systemctl --user enable --now uav-gap-watch.timer 2>/dev/null \
  && echo "  gap-watch timer 已启用 (08:30 每日)" \
  || echo "  WARN: timer 未启用（可手动执行 scripts/gap_watch.py）"

if [ "$SKIP_PX4" = "1" ]; then step "跳过 5-6/7 (PX4 栈)"; else

step "5/7 Gazebo Harmonic"
if command -v gz >/dev/null && gz sim --versions >/dev/null 2>&1; then
  echo "  已安装: gz $(gz sim --versions | head -1)"
else
  sudo apt-get update -qq
  sudo apt-get install -y -qq curl lsb-release gnupg
  sudo curl -fsSL https://packages.osrfoundation.org/gazebo.gpg --dearmor \
    -o /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
  sudo apt-get update -qq && sudo apt-get install -y -qq gz-harmonic
fi

step "6a/7 PX4-Autopilot v1.16（首次构建 10~40 分钟）"
if [ ! -d "$HOME/PX4-Autopilot" ]; then
  git clone https://github.com/PX4/PX4-Autopilot.git ~/PX4-Autopilot --recursive
fi
cd ~/PX4-Autopilot
git checkout -q v1.16.0 2>/dev/null || echo "  WARN: v1.16.0 不存在，用默认分支"
bash ./Tools/setup/ubuntu.sh --no-nuttx || true
if [ ! -f build/px4_sitl_default/bin/px4 ]; then
  make px4_sitl
fi

step "6b/7 uXRCE-DDS Agent"
if ! command -v MicroXRCEAgent >/dev/null && [ ! -x "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" ]; then
  git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git ~/Micro-XRCE-DDS-Agent
  cmake -S ~/Micro-XRCE-DDS-Agent -B ~/Micro-XRCE-DDS-Agent/build
  make -C ~/Micro-XRCE-DDS-Agent/build -j"$(nproc)" && sudo make -C ~/Micro-XRCE-DDS-Agent/build install
fi
sudo ln -sf "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" /usr/local/bin/MicroXRCEAgent 2>/dev/null || true

step "6c/7 px4_ros2_ws (px4_msgs + px4_ros_com)"
if [ ! -f "$HOME/px4_ros2_ws/install/setup.bash" ]; then
  mkdir -p ~/px4_ros2_ws/src && cd ~/px4_ros2_ws/src
  [ -d px4_msgs ]     || git clone https://github.com/PX4/px4_msgs.git
  [ -d px4_ros_com ]  || git clone https://github.com/PX4/px4_ros_com.git
  BRANCH="release/1.16"
  for r in px4_msgs px4_ros_com; do
    git -C "$r" checkout -q "$BRANCH" 2>/dev/null || \
      { git -C "$r" fetch -q origin "$BRANCH"; git -C "$r" checkout -q -B "$BRANCH" "origin/$BRANCH"; }
  done
  cd ~/px4_ros2_ws && unset GZ_SIM_RESOURCE_PATH SDF_PATH LD_LIBRARY_PATH || true
  colcon build --symlink-install
fi
fi

step "7/7 MCP servers（rosbags-mcp / ros-mcp）"
echo "  见 docs/WORKFLOW.md §MCP —— 单独安装并写入 .mcp.json（本脚本不重复处理）"

step "完成。验收: ./scripts/sim_launch.sh --headless 后看 READY"
