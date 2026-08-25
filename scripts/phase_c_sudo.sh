#!/usr/bin/env bash
# phase_c_sudo.sh — 需要密码的安装步骤（只需跑一次）  v2（修复 keyring 下载方式）
# 内容: Gazebo Harmonic 安装 + PX4 编译依赖 + uXRCE Agent 系统级安装
set -euo pipefail

echo "[1/3] Gazebo Harmonic 源与安装"
# gazebo.gpg 已是二进制 keyring 格式，直接落盘即可（勿加 --dearmor，那不是 curl 选项）
sudo curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
  -o /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
sudo apt-get update -qq 2>&1 | grep -v "asus-linux\|trusted.gpg" || true
sudo apt-get install -y -qq gz-harmonic

echo "[2/3] PX4 依赖（ubuntu.sh --no-nuttx，纯 SITL）"
bash "$HOME/PX4-Autopilot/Tools/setup/ubuntu.sh" --no-nuttx

echo "[3/3] uXRCE-DDS Agent 系统级安装"
if [ -f "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" ]; then
  sudo make -C "$HOME/Micro-XRCE-DDS-Agent/build" install >/dev/null 2>&1 \
    || sudo cp "$HOME/Micro-XRCE-DDS-Agent/build/MicroXRCEAgent" /usr/local/bin/
  echo "  agent -> $(command -v MicroXRCEAgent || echo /usr/local/bin/MicroXRCEAgent)"
else
  echo "  SKIP: agent 未构建（workflow 侧已完成本地构建，正常不会走到这里）"
fi

echo "DONE — 回到 agent 继续 px4_sitl 构建"
