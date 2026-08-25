#!/usr/bin/env bash
# phase_c_sudo.sh — 需要密码的安装步骤（只需跑一次）
# 内容: Gazebo Harmonic 安装 + PX4 编译依赖
set -euo pipefail

echo "[1/3] Gazebo Harmonic 源与安装"
sudo apt-get update -qq
sudo apt-get install -y -qq curl lsb-release gnupg wget ca-certificates
sudo curl -fsSL https://packages.osrfoundation.org/gazebo.gpg --dearmor \
  -o /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
sudo apt-get update -qq
sudo apt-get install -y -qq gz-harmonic

echo "[2/3] PX4 依赖（ubuntu.sh --no-nuttx，纯 SITL）"
bash "$HOME/PX4-Autopilot/Tools/setup/ubuntu.sh" --no-nuttx

echo "[3/3] uXRCE-DDS Agent 系统级安装"
if [ -f "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" ]; then
  sudo "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" --help >/dev/null 2>&1 || true
  sudo make -C "$HOME/Micro-XRCE-DDS-Agent/build" install || \
    sudo ln -sf "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" /usr/local/bin/MicroXRCEAgent
else
  echo "  先等 workflow 侧完成 agent 本地构建，再重跑本脚本第3步"
fi

echo "DONE — 回到 agent 继续后续构建"
