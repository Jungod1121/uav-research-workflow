---
name: experiment-setup
description: UAV 仿真实验环境的安装、版本钉死与排障。涵盖 ROS2 Humble + Gazebo Harmonic + PX4 v1.16 + uXRCE-DDS 栈，含已知坑清单。触发词：搭环境、装PX4、装Gazebo、环境坏了、版本冲突、setup experiment。
---

# Experiment Setup — 环境基线与钉版本

本机基线（2026-08 实测）：Ubuntu 22.04 · ROS 2 Humble · Python 3.10 · 无 Docker。
**版本一经钉死不得随意升级**；任何变更记录到本文档末尾的变更日志。

## 钉死的版本组合（Humble 路线）

| 组件 | 版本 | 安装方式 |
|---|---|---|
| Ubuntu | 22.04 | 系统 |
| ROS 2 | Humble（/opt/ros/humble） | apt |
| Gazebo | Harmonic（gz-sim8） | osrfoundation apt 源 |
| PX4-Autopilot | v1.16 release 分支 | ~/PX4-Autopilot 源码 |
| px4_msgs / px4_ros_com | release/1.16 分支（tag v1.16.0 对应） | colcon ws 源码编译 |
| Micro XRCE-DDS Agent | v2.4.3+ | 源码或 snap |
| ros_gz | humble↔harmonic 组合（按需，图像话题桥接用） | 源码 |

> 迁移路径：2026 主流为 Ubuntu24.04+Jazzy+Harmonic。等 Humble EOL(2027-05) 前再迁，届时优先 Docker 方案而非升系统。

## 标准安装序列（provision.sh 自动执行，此处供手工修复参考）

```bash
# 1. Gazebo Harmonic
sudo apt install curl lsb-release gnupg
sudo curl https://packages.osrfoundation.org/gazebo.gpg --dearmor -o /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list
sudo apt update && sudo apt -y install gz-harmonic

# 2. PX4 依赖 + 源码（--no-nuttx：纯 SITL 不装交叉工具链，省 3GB）
bash -c "cd ~ && git clone https://github.com/PX4/PX4-Autopilot.git --recursive"
bash ~/PX4-Autopilot/Tools/setup/ubuntu.sh --no-nuttx
cd ~/PX4-Autopilot && make px4_sitl    # 首次构建 10~40 分钟

# 3. uXRCE-DDS Agent
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git ~/Micro-XRCE-DDS-Agent
cd ~/Micro-XRCE-DDS-Agent && mkdir build && cd build && cmake .. && make -j$(nproc) && sudo make install

# 4. ROS 侧消息与接口
mkdir -p ~/px4_ros2_ws/src && cd ~/px4_ros2_ws/src
git clone https://github.com/PX4/px4_msgs.git && git clone https://github.com/PX4/px4_ros_com.git
# ⚠️ 两个仓库都要 checkout release/1.16 分支（对应固件 tag v1.16.0）
cd ~/px4_ros2_ws && source /opt/ros/humble/setup.bash && colcon build
```

## 已知坑清单（遇到对应症状先查这里）

| 症状 | 原因 | 处置 |
|---|---|---|
| Gazebo GUI 一打开就锁定跟随视角 | PX4 默认开启 follow camera | 启动加 `PX4_GZ_NO_FOLLOW=1` |
| colcon build 报 GZ_SIM_RESOURCE_PATH 相关错误 | 继承了其他仿真环境(ArduPilot等)的环境变量 | 构建前 `unset GZ_SIM_RESOURCE_PATH SDF_PATH LD_LIBRARY_PATH` |
| `/fmu/out/*` 话题全空 | uXRCE Agent 没起或端口不对 | Agent: `MicroXRCEAgent udp4 -p 8888`；确认 PX4 日志出现 `uxrce_dds_client` 连接成功 |
| px4_msgs 编译报 CRC/version 错 | msg 版本与固件不匹配 | 两边切同一 release 分支后全量重编 |
| 二次启动无世界文件/模型找不到 | 模型路径缓存问题 | `export GZ_SIM_RESOURCE_PATH=$HOME/PX4-Autopilot/Tools/simulation/gz/models:...`（见 sim_launch.sh） |
| DDS 串台收到别人的话题 | ROS_DOMAIN_ID 冲突 | 本工作流固定 `ROS_DOMAIN_ID=77`，sim_launch.sh 已内置 |
| 订阅端收不到消息, 日志报 incompatible QoS (RELIABILITY) | rclpy 默认 RELIABLE, PX4 uXRCE 发布端是 BEST_EFFORT | 订阅用 BEST_EFFORT QoSProfile（square_offboard.py 已内置） |
| 话题名带版本后缀(如 vehicle_status_v1) | PX4 v1.16+ 启用消息版本化命名 | 用 `ros2 topic list` 确认实际名; 类型不变 |
| Preflight Fail: No connection to the ground control station | SITL 机架默认 NAV_DLL_ACT=2 要求 GCS 在线 | 4001_gz_x500 已改为 NAV_DLL_ACT=0(无QGC环境); 重装 PX4 后需重打 |
| Preflight Fail: ekf2 missing data | 刚启动 EKF 未收敛 | 起飞前等 10~15s(square_offboard 已内置) |
| 手动分离启动 gz server + px4 二进制 | 破坏 lockstep 握手: 世界被暂停, 传感器系统不激活, EKF 永远缺数据 | 必须用 `make px4_sitl gz_x500` 协调启动(sim_launch.sh 已内置) |
| px4 shell 刷 10GB 日志 | make 的 stdin=EOF 时 px4 shell 疯狂打印提示符 | 启动命令用 `tail -f /dev/null \| make ...` 保活 stdin |
| rviz2/gz GUI 崩溃 GLXContext unable to create | NVIDIA 驱动/库版本不匹配(unattended-upgrades 后未重启) | sim_launch 已自动回退 Mesa 软渲染; 根治=reboot |
| `gz sim -r`(server+GUI 同进程) 整体崩 | GUI 的 GLX 崩溃会带走 server | sim_launch 已改为 server 恒 HEADLESS + GUI 客户端分离 |
| 残留进程导致下次起不来 | 上次异常退出 | `sim_stop.sh`（内部 pkill 全家桶），跑新实验前必查 |

## 可选组件（按需引入，勿提前安装）

- **flightmare**：敏捷飞行需特定动力学保真度时；注意上游 2022 年后维护缓慢;
- **Isaac Lab**：VLA/RL 训练数据量上量后才引入；
- **mavros2**：仅当需要 MAVLink 层协议（uXRCE 已覆盖大部分场景）；
- **pyrealsense2**：真机 RealSense 时。

## 验收命令（环境健康检查一条龙）

```bash
source /opt/ros/humble/setup.bash && source ~/px4_ros2_ws/install/setup.bash
ros2 topic list | grep /fmu   # 有输出 = PX4↔ROS2 通了
```

## 变更日志

- 2026-08-24 初始钉版：Humble + Harmonic + PX4 v1.16（workflow 初建）

### L2.5 真深度闭环坑 (2026-09-04, v28)
- **PX4_GZ_WORLD 内部名必须等于文件名**: rcS 等待 `/world/<文件名>/scene/info`, 名字不一致则 PX4 永远卡 "Waiting for Gazebo world" (0% CPU, lockstep 空等)
- **孤儿进程竞态**: PX4 崩溃 (exit 255) 后 gz/agent 常成孤儿; 重启栈时 rcS 探到 "already running world" 会复用垂死 gz → 必须先 `pkill -f "gz si[m]"` 等全部清零再启动
- **pkill 自匹配**: 同一命令行含目标字面量时会自杀; 用 `pkill -f "gz si[m]"` 括号技巧且目标字面量不得出现在同一命令行
- **/traj_start_trigger 是 geometry_msgs/PoseStamped** (非 Empty); FSM 在 WAIT_TARGET 静默丢弃类型不匹配的触发
- **ros2 CLI wait-set 报错**: daemon 中毒后 `ros2 daemon stop` 仍可能报 rcl context 错 → 用 python 一次性订阅探测代替 CLI
- **世界级 plugin 声明会屏蔽 server.config 默认系统**; PX4 世界不含系统插件 (模型级传感器自持), 自建世界以 default.sdf 为骨架最稳
- ros_gz 源码构建 (humble+harmonic): 需补 actuator_msgs(rudislabs)/gps_umd(swri)/vision_msgs(ros-perception 注意非 ros2 org), 跳过 gpsd_client/gps_tools/gps_umd/vision_msgs_rviz_plugins
