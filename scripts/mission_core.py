#!/usr/bin/env python3
"""mission_core.py — PX4 offboard 任务状态机(公共模块)。

官方契约(https://docs.px4.io/main/en/flight_modes/offboard):
  - OffboardControlMode 是心跳: >2Hz 持续流, 中断超 COM_OF_LOSS_T 触发 failsafe
  - 切换/解锁前必须预流 >=1s
  - ARM/模式切换必须 ACK 确认(重试直到成功), 不允许"发了就算"
多机约定(https://docs.px4.io/main/en/ros2/multi_vehicle):
  - instance=0 无前缀(/fmu/); instance>0 自动 px4_N 前缀 -> 本类用 namespace 参数显式对齐
"""
import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import (TrajectorySetpoint, OffboardControlMode, VehicleCommand,
                          VehicleLocalPosition, VehicleStatus, VehicleCommandAck)

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)
HEARTBEAT_HZ = 20          # 官方要求 >2Hz, 取 20Hz 冗余
PRESTREAM_S = 1.5          # 官方要求 >=1s
ACK_TIMEOUT_S = 12         # ARM/模式切换 ACK 重试窗口


class OffboardMission(Node):
    """单机 offboard 状态机。namespace="" -> /fmu/; namespace="px4_1" -> /px4_1/fmu/"""

    def __init__(self, name="mission", namespace="", mav_sys_id=1):
        super().__init__(name)
        ns = f"/{namespace}" if namespace else ""
        self.mode_pub = self.create_publisher(OffboardControlMode, f"{ns}/fmu/in/offboard_control_mode", 10)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, f"{ns}/fmu/in/trajectory_setpoint", 10)
        self.cmd_pub = self.create_publisher(VehicleCommand, f"{ns}/fmu/in/vehicle_command", 10)
        self.create_subscription(VehicleLocalPosition, f"{ns}/fmu/out/vehicle_local_position", self._on_pos, QOS)
        self.create_subscription(VehicleStatus, f"{ns}/fmu/out/vehicle_status_v1", self._on_status, QOS)
        self.acks = []
        self.acked_cmd = None
        self.height = None
        self.pos = None
        self.nav_state = None
        self.create_subscription(VehicleCommandAck, f"{ns}/fmu/out/vehicle_command_ack", self._on_ack, QOS)
        self.mav_sys_id = int(mav_sys_id)   # 多机: 必须与目标机的 MAV_SYS_ID 一致, 否则命令被忽略
        self.metrics = {"events": [], "namespace": namespace, "mav_sys_id": self.mav_sys_id}
        self.t0 = time.time()

    # ---------- 基础 ----------
    def t(self):
        return round(time.time() - self.t0, 2)

    def _on_pos(self, m):
        self.pos = m

    def _on_status(self, m):
        if self.nav_state != m.nav_state:
            self.metrics["events"].append({"t": self.t(), "e": f"nav={m.nav_state}"})
            self.nav_state = m.nav_state

    def _on_ack(self, m):
        self.acked_cmd = (m.command, m.result)
        self.acks.append(self.acked_cmd)

    def spin(self, sec):
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    # ---------- 官方契约: 心跳 + 设定点 ----------
    def heartbeat(self, sp=None):
        m = OffboardControlMode(); m.position = True
        m.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        self.mode_pub.publish(m)
        if sp is not None:
            s = TrajectorySetpoint(); s.position = [float(sp[0]), float(sp[1]), -abs(float(sp[2]))]; s.yaw = 0.0
            s.timestamp = m.timestamp
            self.sp_pub.publish(s)

    def _cmd_with_ack(self, command, p1=0.0, p2=0.0, expect_result=0, sp=None):
        """发命令并等待 ACK; 重试期间持续发心跳(否则 COM_OF_LOSS_T 触发 failsafe)。"""
        self.acked_cmd = None
        deadline = time.time() + ACK_TIMEOUT_S
        last_send = 0
        while time.time() < deadline:
            self.heartbeat(sp)  # 心跳不能断: offboard 丢失即 failsafe
            if time.time() - last_send > 2.0:
                v = VehicleCommand(); v.command = command; v.param1 = float(p1); v.param2 = float(p2)
                v.target_system = self.mav_sys_id; v.target_component = 1
                v.timestamp = int(self.get_clock().now().nanoseconds / 1000)
                self.cmd_pub.publish(v)
                last_send = time.time()
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.acked_cmd and self.acked_cmd[0] == command:
                if self.acked_cmd[1] == expect_result:
                    return self.acked_cmd[1]
                self.acked_cmd = None  # 被拒, 继续重试
        return None

    # ---------- 状态机 ----------
    def preflight(self, timeout=60):
        """PREFLIGHT: 等位置有效 + EKF 收敛。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.5)
            if self.pos and self.pos.xy_valid and self.pos.z_valid:
                self.metrics["events"].append({"t": self.t(), "e": "position_valid"})
                self.spin(10)  # EKF 稳定窗
                self.metrics["events"].append({"t": self.t(), "e": "ekf_settle_done"})
                return True
        self.metrics["events"].append({"t": self.t(), "e": "preflight_timeout"})
        return False

    def arm_and_engage(self, home_xy, height):
        """预流 -> 切 OFFBOARD(ACK 确认) -> ARM(ACK 确认)。返回是否成功。"""
        self.metrics["events"].append({"t": self.t(), "e": "prestream_start"})
        end = time.time() + PRESTREAM_S
        while time.time() < end:
            self.heartbeat(home_xy + (height,)); rclpy.spin_once(self, timeout_sec=0.05)
        r1 = self._cmd_with_ack(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1, 6, sp=home_xy + (height,))
        self.metrics["events"].append({"t": self.t(), "e": f"offboard_ack={r1}"})
        r2 = self._cmd_with_ack(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1, sp=home_xy + (height,))
        self.metrics["events"].append({"t": self.t(), "e": f"arm_ack={r2}"})
        return r1 == 0 and r2 == 0

    def fly_waypoints(self, home_xy, height, waypoints, wp_tol=0.35, speed_hint=None, wp_timeout=90):
        """EXECUTE: 依次到达航点(含中点插值的路径由调用方展开)。返回(到达数, 详情)。"""
        reached = 0
        details = []
        for i, (dx, dy) in enumerate(waypoints, 1):
            tx, ty = home_xy[0] + dx, home_xy[1] + dy
            ok, err = self._goto(tx, ty, height, wp_tol, wp_timeout)
            details.append({"wp": i, "target": [round(tx, 2), round(ty, 2)],
                            "reached": ok, "err_m": round(err, 3), "t": self.t()})
            reached += 1 if ok else 0
        return reached, details

    def _goto(self, x, y, z, tol, timeout):
        deadline = time.time() + timeout
        entered = False
        while time.time() < deadline:
            self.heartbeat((x, y, z)); rclpy.spin_once(self, timeout_sec=0.05)
            if not self.pos:
                continue
            err = math.hypot(self.pos.x - x, self.pos.y - y)
            if err <= tol:
                stable = True
                for _ in range(15):  # ~0.75s 稳定确认
                    self.heartbeat((x, y, z)); rclpy.spin_once(self, timeout_sec=0.05)
                    if not self.pos or math.hypot(self.pos.x - x, self.pos.y - y) > tol:
                        stable = False; break
                if stable:
                    return True, err
                entered = True
            elif entered:
                entered = False
        return False, 999.0

    def land_and_finish(self, out_path, height=2.5):
        self.heartbeat((self.pos.x if self.pos else 0, self.pos.y if self.pos else 0, height))
        self._cmd_with_ack(VehicleCommand.VEHICLE_CMD_NAV_LAND)
        self.spin(6)
        self._cmd_with_ack(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0)
        self.metrics["events"].append({"t": self.t(), "e": "land_cmd_sent"})
        with open(out_path, "w") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        print(f"METRICS_SAVED {out_path}")


def spin_node(node, sec):
    end = time.time() + sec
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
