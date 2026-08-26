#!/usr/bin/env python3
"""mission_follower.py — A2 编队: 跟随 Leader 保持相对偏移 (默认东向 2m)。
用法: mission_follower.py <metrics_out.json> [height=2.5] [follow_s=45] [off_x=2] [off_y=0] [ns=px4_1] [sys_id=2]
"""
import math
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleLocalPosition, VehicleCommand
from mission_core import OffboardMission

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)


def main():
    out = sys.argv[1]
    kv = dict(x.split("=", 1) for x in sys.argv[2:] if "=" in x)
    height = float(kv.get("height", 2.5))
    follow_s = float(kv.get("follow_s", 45))
    off = (float(kv.get("off_x", 2.0)), float(kv.get("off_y", 0.0)))
    ns = kv.get("ns", "px4_1")
    sys_id = kv.get("sys_id", "2")

    rclpy.init()
    f = OffboardMission("follower", namespace=ns, mav_sys_id=sys_id)
    f.height = height

    # Leader 位置订阅(独立节点回调挂在 follower 节点上, 共享 executor)
    leader = {"x": None, "y": None}
    f.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position",
                          lambda m: leader.update(x=m.x, y=m.y), QOS)

    # PREFLIGHT: 自身位置有效
    deadline = time.time() + 60
    while time.time() < deadline and not (f.pos and f.pos.xy_valid and f.pos.z_valid):
        rclpy.spin_once(f, timeout_sec=0.5)
    if not f.pos:
        print("MISSION_FAILED follower_no_position"); return 1
    time.sleep(10)  # EKF
    fx0, fy0 = f.pos.x, f.pos.y

    # 等 Leader 起飞(其位置开始变化或直接用当前位置)
    deadline = time.time() + 40
    while time.time() < deadline and leader["x"] is None:
        rclpy.spin_once(f, timeout_sec=0.2)
    if leader["x"] is None:
        print("MISSION_FAILED no_leader_position"); return 1

    # 初始设定点 = Leader 当前位置 + 偏移(等高)
    lx, ly = leader["x"], leader["y"]
    f.metrics["events"].append({"t": f.t(), "e": "prestream_start"})
    end = time.time() + 1.5
    while time.time() < end:
        f.heartbeat((lx + off[0], ly + off[1], height)); rclpy.spin_once(f, timeout_sec=0.05)

    ok = _engage(f, lx + off[0], ly + off[1], height)
    if not ok:
        f.land_and_finish(out, height); print("MISSION_FAILED follower_engage"); return 1

    # 跟随环
    f.metrics["events"].append({"t": f.t(), "e": "following_start"})
    errs = []
    end = time.time() + follow_s
    while time.time() < end and rclpy.ok():
        if leader["x"] is not None:
            f.heartbeat((leader["x"] + off[0], leader["y"] + off[1], height))
        rclpy.spin_once(f, timeout_sec=0.05)
        if f.pos and leader["x"] is not None:
            err = math.hypot(f.pos.x - (leader["x"] + off[0]),
                             f.pos.y - (leader["y"] + off[1]))
            errs.append(err)
    f.metrics["tracking"] = {
        "offset": list(off), "samples": len(errs),
        "err_mean_m": round(sum(errs) / len(errs), 3) if errs else None,
        "err_max_m": round(max(errs), 3) if errs else None,
    }
    f.metrics["events"].append({"t": f.t(), "e": "following_done"})

    f.land_and_finish(out, height)
    print(f"MISSION_DONE {out}")
    return 0


def _engage(f, x, y, height):
    """复用 mission_core 的切换+解锁序列(带 ACK 重试与心跳)。"""
    end = time.time() + 1.0
    while time.time() < end:
        f.heartbeat((x, y, height)); rclpy.spin_once(f, timeout_sec=0.05)
    r1 = f._cmd_with_ack(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1, 6, sp=(x, y, height))
    r2 = f._cmd_with_ack(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1, sp=(x, y, height))
    return r1 == 0 and r2 == 0


if __name__ == "__main__":
    sys.exit(main())
