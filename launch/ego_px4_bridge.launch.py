#!/usr/bin/env python3
"""ego_px4_bridge.launch.py — EGO-Planner 接 PX4 真感知 (B4-full)。

不含任何仿真节点: 里程计来自 /px4_ego/odom (px4_ego_bridge.py), 深度来自
/px4_ego/depth (ros_gz_bridge 重映射 x500_depth 的 /depth_camera)。
航点穿过森林: (12,0,1.5) -> (-12,0,1.5), 通过 /traj_start_trigger 触发。

用法: ros2 launch launch/ego_px4_bridge.launch.py
"""
import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

ADV = os.path.join(get_package_share_directory("ego_planner"), "launch", "advanced_param.launch.py")


def generate_launch_description():
    drone_id = "0"
    advanced = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ADV),
        launch_arguments={
            "drone_id": drone_id,
            "map_size_x_": "40.0",
            "map_size_y_": "24.0",
            "map_size_z_": "3.0",
            "odometry_topic": "/px4_ego/odom",
            "obj_num_set": "5",
            "camera_pose_topic": "/px4_ego/camera_pose",
            "depth_topic": "/px4_ego/depth",
            "cloud_topic": "/px4_ego/cloud",
            # OakD-Lite: 640x480, HFOV 1.274 rad
            "cx": "320.0",
            "cy": "240.0",
            "fx": "432.5",
            "fy": "432.5",
            "max_vel": "1.5",
            "max_acc": "4.0",
            "planning_horizon": "6.0",
            "use_distinctive_trajs": "False",
            "flight_type": "2",
            "point_num": "1",
            "point0_x": "-12.0",
            "point0_y": "0.0",
            "point0_z": "1.5",
            "point1_x": "-12.0",
            "point1_y": "0.0",
            "point1_z": "1.5",
        }.items(),
    )

    traj_server = Node(
        package="ego_planner",
        executable="traj_server",
        name=["drone_", drone_id, "_traj_server"],
        output="screen",
        remappings=[
            ("position_cmd", ["drone_", drone_id, "_planning/pos_cmd"]),
            ("planning/bspline", ["drone_", drone_id, "_planning/bspline"]),
        ],
        parameters=[{"traj_server/time_forward": 1.0}],
    )

    return LaunchDescription([advanced, traj_server])
