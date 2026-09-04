#!/usr/bin/env python3
"""sim_stack.launch.py — v2 架构: 单一入口声明式编排仿真栈。

职责划分(与旧 bash 编排的本质区别):
  - PX4 SITL 进程自己管理 gz server 生命周期(rcS 内 px4-rc.gzsim), 我们不抢
  - ros2 launch 管所有子进程生命周期: 崩溃可见、SIGINT 干净关停、无孤儿
  - 本文件不做任何"探测/重试/杀进程" — 那些是上层(probe/mission)的事

用法: ros2 launch launch/sim_stack.launch.py
"""
import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction

PX4_DIR = Path.home() / "PX4-Autopilot"
AGENT_BIN = Path.home() / "Micro-XRCE-DDS-Agent" / "build" / "MicroXRCEAgent"

HEADLESS = os.environ.get("STACK_HEADLESS", "1")  # 1=仅 server; 0=rcS 另起 GUI(需 GL 健康)
INSTANCES = int(os.environ.get("STACK_INSTANCES", "1"))  # 1=单机; 2=双机(官方 -i/namespace 约定)

PX4_ENV = {
    "PX4_SIM_MODEL": os.environ.get("STACK_PX4_MODEL", "gz_x500"),
    "PX4_SYS_AUTOSTART": "4001",
    "HEADLESS": HEADLESS,
    "PX4_GZ_NO_FOLLOW": "1",
    "ROS_DOMAIN_ID": "77",
    "GZ_VERSION": "harmonic",
    "GZ_IP": "127.0.0.1",
    "GZ_IP": "127.0.0.1",  # gz-transport 发现统一回环
    "PX4_GZ_WORLD": os.environ.get("STACK_GZ_WORLD", "default"),
    "FASTDDS_BUILTIN_TRANSPORTS": "UDPv4",  # 禁 SHM: pkill 残段会让 DDS 数据交换间歇性挂起
}


def generate_launch_description():
    # 1) uXRCE-DDS Agent: px4 <-> ROS2 的桥(纯 UDP 127.0.0.1:8888, 无发现机制依赖)
    agent = ExecuteProcess(
        cmd=[str(AGENT_BIN), "udp4", "-p", "8888"],
        output="log",
    )

    # 2) PX4 SITL(内部拉起 gz server): 延迟 2s 保证 agent 先就绪
    px4 = ExecuteProcess(
        cmd=[str(PX4_DIR / "build" / "px4_sitl_default" / "bin" / "px4")],
        cwd=str(PX4_DIR),
        additional_env=PX4_ENV,
        output="log",
    )

    px4_delayed = TimerAction(period=2.0, actions=[px4])

    # 实例 1(第二架): 官方多机约定 -> -i 1 + MAV_SYS_ID=2, 自动命名空间 /px4_1/fmu/
    # UXRCE_DDS_KEY 自动 = instance+1 = 2; PX4_GZ_MODEL_POSE 错开出生点防碰撞
    px4_env_1 = dict(PX4_ENV, MAV_SYS_ID="2", PX4_GZ_MODEL_POSE="0,2")
    px4_1 = ExecuteProcess(
        cmd=[str(PX4_DIR / "build" / "px4_sitl_default" / "bin" / "px4"), "-i", "1"],
        cwd=str(PX4_DIR),
        additional_env=px4_env_1,
        output="log",
    )
    px4_1_delayed = TimerAction(period=8.0, actions=[px4_1])

    actions = [agent, px4_delayed]
    if INSTANCES >= 2:
        actions.append(px4_1_delayed)
    return LaunchDescription(actions)
