#!/usr/bin/env python3
"""mission_takeoff_hold.py — 最小单机任务: 起飞 -> 位置保持 -> 降落。

用户方向: 先跑通"起飞+位置控制", 再谈任务与多机。
用法: mission_takeoff_hold.py <height_m> <hold_s> <metrics_out.json>
"""
import json
import math
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import TrajectorySetpoint, OffboardControlMode, VehicleCommand, VehicleLocalPosition, VehicleStatus

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)


class TakeoffHold(Node):
    def __init__(self, height, hold_s, out_path):
        super().__init__("mission_takeoff_hold")
        self.height, self.hold_s, self.out_path = height, hold_s, out_path
        self.mode_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", 10)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", 10)
        self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position", self.on_pos, QOS)
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status_v1", self.on_status, QOS)
        self.pos = None
        self.nav_state = None
        self.metrics = {"height": height, "hold_s": hold_s, "events": [], "drift_max_m": 0.0}
        self.t0 = time.time()

    def t(self):
        return round(time.time() - self.t0, 2)

    def on_pos(self, m):
        self.pos = m

    def on_status(self, m):
        if self.nav_state != m.nav_state:
            self.metrics["events"].append({"t": self.t(), "e": f"nav={m.nav_state}"})
            self.nav_state = m.nav_state

    def stream(self, x, y, z):
        m = OffboardControlMode(); m.position = True
        m.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.mode_pub.publish(m)
        sp = TrajectorySetpoint(); sp.position = [x, y, -abs(z)]; sp.yaw = 0.0
        sp.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.sp_pub.publish(sp)

    def cmd(self, c, p1=0.0, p2=0.0):
        v = VehicleCommand(); v.command = c; v.param1 = float(p1); v.param2 = float(p2)
        v.target_system = 1; v.target_component = 1
        v.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.cmd_pub.publish(v)

    def run(self):
        deadline = time.time() + 60
        while time.time() < deadline and not (self.pos and self.pos.xy_valid and self.pos.z_valid):
            rclpy.spin_once(self, timeout_sec=0.5)
        if not self.pos:
            print("MISSION_FAILED no_local_position"); return 1
        time.sleep(10)  # EKF 收敛

        x0, y0 = self.pos.x, self.pos.y
        self.metrics["events"].append({"t": self.t(), "e": "takeoff_start"})
        for _ in range(30):  # 预流 >1s
            self.stream(x0, y0, self.height); rclpy.spin_once(self, timeout_sec=0.05)
        self.cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1, 6)
        time.sleep(0.3)
        self.cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1)
        self.metrics["events"].append({"t": self.t(), "e": "arm_sent"})

        t_end = time.time() + self.hold_s
        while time.time() < t_end and rclpy.ok():
            self.stream(x0, y0, self.height)
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.pos:
                d = math.hypot(self.pos.x - x0, self.pos.y - y0)
                self.metrics["drift_max_m"] = max(self.metrics["drift_max_m"], round(d, 3))
        self.metrics["events"].append({"t": self.t(), "e": "hold_done"})

        self.cmd(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        time.sleep(6)
        self.cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0)
        with open(self.out_path, "w") as f:
            json.dump(self.metrics, f, indent=2)
        print(f"MISSION_DONE {self.out_path}")
        return 0


def main():
    height, hold_s, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
    rclpy.init()
    node = TakeoffHold(height, hold_s, out)
    rc = node.run()
    node.destroy_node(); rclpy.shutdown()
    sys.exit(rc)


if __name__ == "__main__":
    main()
