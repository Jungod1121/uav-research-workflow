#!/usr/bin/env python3
"""square_offboard.py — 方框航点 offboard 任务（PX4 v1.16 / ROS2 Humble）

流程: 等待本地位置有效 -> 起飞到目标高度 -> 依次飞方框四角(回到起点)
      -> 原地降落 -> 落盘 metrics.json
输出: MISSION_DONE <metrics_json_path> 或 MISSION_FAILED <reason>
"""
import json
import math
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import TrajectorySetpoint, OffboardControlMode, VehicleCommand, VehicleLocalPosition, VehicleStatus

# PX4 uXRCE 发布端为 BEST_EFFORT，订阅端必须匹配（坑清单）
QOS_BEST_EFFORT = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                             history=HistoryPolicy.KEEP_LAST, depth=10)


class SquareOffboard(Node):
    def __init__(self, side, height, speed, wp_tol):
        super().__init__("square_offboard")
        self.side, self.height = float(side), float(height)
        self.speed = float(speed)
        self.wp_tol = float(wp_tol)

        self.offboard_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", 10)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", 10)
        self.pos_sub = self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position",
                                                self.on_pos, QOS_BEST_EFFORT)
        self.status_sub = self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status",
                                                   self.on_status, QOS_BEST_EFFORT)
        self.nav_state = None

        # 方框航点（相对起飞点，NED: x 北 y 东）
        s = self.side
        self.waypoints = [(s, 0.0), (s, s), (0.0, s), (0.0, 0.0)]
        self.metrics = {"side": s, "height": self.height, "speed": self.speed,
                        "waypoints": [], "events": []}
        self.pos = None
        self.start_ns = time.time()

    def t(self):
        return round(time.time() - self.start_ns, 2)

    def on_pos(self, msg):
        self.pos = msg

    def on_status(self, msg):
        if self.nav_state != msg.nav_state:
            self.metrics["events"].append({"t": self.t(), "event": f"nav_state={msg.nav_state}"})
            self.get_logger().info(f"nav_state -> {msg.nav_state} (6=OFFBOARD)")
            self.nav_state = msg.nav_state

    # ---------- 基础发布 ----------
    def publish_mode(self):
        m = OffboardControlMode()
        m.position = True
        m.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.offboard_pub.publish(m)

    def publish_sp(self, x, y, z):
        sp = TrajectorySetpoint()
        sp.position = [float(x), float(y), -abs(float(z))]   # NED 向下为正 -> 高度取负
        sp.yaw = 0.0
        sp.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.sp_pub.publish(sp)

    def send_cmd(self, cmd, p1=0.0, p2=0.0):
        c = VehicleCommand()
        c.command = cmd
        c.param1 = float(p1)
        c.param2 = float(p2)
        c.target_system = 1
        c.target_component = 1
        c.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.cmd_pub.publish(c)

    def wait_pos_valid(self, timeout=60):
        self.get_logger().info("waiting for valid local position ...")
        deadline = time.time() + timeout
        while rclpy.ok() and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.5)
            if self.pos and self.pos.xy_valid and self.pos.z_valid:
                return True
        return False

    def stream_hold(self, x, y, z, seconds):
        end = time.time() + seconds
        while time.time() < end and rclpy.ok():
            self.publish_mode(); self.publish_sp(x, y, z)
            rclpy.spin_once(self, timeout_sec=0.05)

    def goto(self, x, y, z, timeout=90):
        """位置设定点巡航，进入容差圈记到达。返回(是否到达, 水平误差序列峰值)。"""
        deadline = time.time() + timeout
        max_err_after_first_in = None
        entered = False
        while time.time() < deadline and rclpy.ok():
            self.publish_mode(); self.publish_sp(x, y, z)
            rclpy.spin_once(self, timeout_sec=0.05)
            if not self.pos:
                continue
            err = math.hypot(self.pos.x - x, self.pos.y - y)
            if err <= self.wp_tol:
                entered = True
                max_err_after_first_in = max(max_err_after_first_in or 0.0,
                                             err) if max_err_after_first_in else err
                # 连续 15 帧(~0.75s)在圈内视为稳定到达
                stable = True
                for _ in range(15):
                    self.publish_mode(); self.publish_sp(x, y, z)
                    rclpy.spin_once(self, timeout_sec=0.05)
                    if not self.pos or math.hypot(self.pos.x - x, self.pos.y - y) > self.wp_tol:
                        stable = False; break
                if stable:
                    return True, err
            elif entered:
                max_err_after_first_in = max(max_err_after_first_in or 0.0, err)
        return False, (max_err_after_first_in if max_err_after_first_in is not None else 999.0)

    # ---------- 任务主体 ----------
    def run(self):
        if not self.wait_pos_valid():
            print("MISSION_FAILED no_local_position"); return 1

        x0, y0 = self.pos.x, self.pos.y
        self.metrics["events"].append({"t": self.t(), "event": "takeoff_start"})
        # 预流 setpoint >1s 后切 offboard（PX4 要求先有流）
        self.stream_hold(x0, y0, self.height, 1.5)
        self.send_cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1, 6)   # OFFBOARD
        time.sleep(0.3)
        self.send_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1)  # ARM
        self.metrics["events"].append({"t": self.t(), "event": "armed"})

        ok_all = True
        for i, (dx, dy) in enumerate(self.waypoints, 1):
            tx, ty = x0 + dx, y0 + dy
            reached, err = self.goto(tx, ty, self.height)
            rec = {"wp": i, "target": [round(tx, 2), round(ty, 2)],
                   "reached": reached, "final_err_m": round(err, 3),
                   "t": self.t()}
            self.metrics["waypoints"].append(rec)
            self.get_logger().info(f"WP{i} target=({tx:.1f},{ty:.1f}) reached={reached} err={err:.2f}m")
            if not reached:
                ok_all = False
                self.metrics["events"].append({"t": self.t(), "event": f"wp{i}_timeout"})
                break

        self.metrics["events"].append({"t": self.t(), "event": "mission_end" if ok_all else "aborted"})
        # 降落：直接 NAV_LAND（当前模式自动处理）
        self.stream_hold(self.pos.x, self.pos.y, self.height, 1.0)
        self.send_cmd(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        time.sleep(5)
        self.send_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0)  # DISARM

        out_path = sys.argv[5]
        with open(out_path, "w") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        print(f"MISSION_DONE {out_path}" if ok_all else f"MISSION_PARTIAL {out_path}")
        return 0


def main():
    side, height, speed, wp_tol = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    rclpy.init()
    node = SquareOffboard(side, height, speed, wp_tol)
    rc = node.run()
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(rc)


if __name__ == "__main__":
    main()
