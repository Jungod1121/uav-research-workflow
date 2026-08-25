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
from launch_ros.actions import Node

PX4_DIR = Path.home() / "PX4-Autopilot"
AGENT_BIN = Path.home() / "Micro-XRCE-DDS-Agent" / "build" / "MicroXRCEAgent"

PX4_ENV = {
    "PX4_SIM_MODEL": "gz_x500",
    "PX4_SYS_AUTOSTART": "4001",
    "HEADLESS": "1",            # rcS 只起 server, GUI 由上层按需另起
    "PX4_GZ_NO_FOLLOW": "1",
    "ROS_DOMAIN_ID": "77",
    "GZ_VERSION": "harmonic",
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

    # 3) rviz2(可选可视化, 崩溃不影响栈; 默认关, 用 rviz:=true 开)
    rviz = Node(
        package="rviz2", executable="rviz2", output="log",
        condition=IfConditionLaunchArg("rviz"),
    )
    rviz_delayed = TimerAction(period=10.0, actions=[rviz])

    return LaunchDescription([
        DeclareLaunchArg("rviz", default_value="false"),
        agent,
        px4_delayed,
        rviz_delayed,
    ])


def DeclareLaunchArg(name, default_value):
    from launch.actions import DeclareLaunchArgument as _D
    from launch.substitutions import LaunchConfiguration as _C
    return _D(name, default_value=default_value), _C(name)


def IfConditionLaunchArg(name):
    from launch.conditions import IfCondition
    from launch.substitutions import LaunchConfiguration as _C
    return IfCondition(_C(name))
