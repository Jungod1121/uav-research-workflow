#!/usr/bin/env python3
"""px4_ego_bridge.py — PX4 odometry (NED/FRD, px4_msgs) → EGO-Planner 输入 (ENU, nav_msgs)。

发布:
  /px4_ego/odom        nav_msgs/Odometry       — FSM/traj_server 用 (FLU body 约定)
  /px4_ego/camera_pose PoseStamped (50Hz)      — grid_map pose_type=1 同步用
相机补偿: OakD 光学帧 (z前向,x右,y下) 相对 FLU 机体的固定旋转已乘入四元数
用法: px4_ego_bridge.py [ns=/fmu]
"""
import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleOdometry
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseStamped

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)

# NED->ENU (含 FRD->FLU): x_e=y_n, y_e=x_n, z_e=-z_n => 180°绕 (1,1,0)/sqrt2
Q_NED2ENU = (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0)  # (w,x,y,z)

# FLU机体 -> 相机光学: 光学z=x_flu(前), 光学x=-y_flu(右), 光学y=-z_flu(下)
# R = [[0,0,1],[-1,0,0],[0,-1,0]] => 180°绕 (1,-1,1)/sqrt3
AX = (1.0, -1.0, 1.0)
n = math.sqrt(sum(a * a for a in AX))
Q_FLU2OPT = (0.0, AX[0] / n, AX[1] / n, AX[2] / n)


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2)


def main():
    ns = sys.argv[1] if len(sys.argv) > 1 else "/fmu"
    rclpy.init()
    node = Node("px4_ego_bridge")
    pub_odom = node.create_publisher(Odometry, "/drone_0_/px4_ego/odom", 10)
    pub_pose = node.create_publisher(PoseStamped, "/drone_0_/px4_ego/camera_pose", 10)
    last_t = [0]

    def on_odo(m: VehicleOdometry):
        stamp = node.get_clock().now().to_msg()
        # 机体姿态: NED->ENU + 机体自身四元数 (px4 q 顺序 wxyz)
        q_body = qmul(Q_NED2ENU, (m.q[0], m.q[1], m.q[2], m.q[3]))
        o = Odometry()
        o.header.stamp = stamp
        o.header.frame_id = "world"
        # NED位置 -> ENU
        o.pose.pose.position.x = float(m.position[1])
        o.pose.pose.position.y = float(m.position[0])
        o.pose.pose.position.z = -float(m.position[2])
        (o.pose.pose.orientation.w, o.pose.pose.orientation.x,
         o.pose.pose.orientation.y, o.pose.pose.orientation.z) = q_body
        o.twist.twist.linear.x = float(m.velocity[1])
        o.twist.twist.linear.y = float(m.velocity[0])
        o.twist.twist.linear.z = -float(m.velocity[2])
        pub_odom.publish(o)

        # 相机位姿: ENU机体姿态 * 机体->光学 旋转 (光学原点=机体原点, 偏移忽略<0.25m)
        p = PoseStamped()
        p.header.stamp = stamp
        p.header.frame_id = "world"
        p.pose.position = o.pose.pose.position
        qc = qmul(q_body, Q_FLU2OPT)
        p.pose.orientation.w, p.pose.orientation.x, p.pose.orientation.y, p.pose.orientation.z = qc
        pub_pose.publish(p)

    node.create_subscription(VehicleOdometry, f"{ns}/out/vehicle_odometry", on_odo, QOS)
    node.get_logger().info("px4_ego_bridge up: /drone_0_/px4_ego/odom + camera_pose")
    rclpy.spin(node)


if __name__ == "__main__":
    main()
