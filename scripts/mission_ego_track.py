#!/usr/bin/env python3
"""mission_ego_track.py — L2: PX4 执行栈跟踪 EGO-Planner 的动态轨迹命令流。

链路: ego traj_server(CycloneDDS, quadrotor_msgs/PositionCommand, ENU)
      → 本节点(跨RMW订阅) → TrajectorySetpoint(FastDDS, NED, pos+vel+acc 前馈)
      → PX4 offboard 执行
指标: 跟踪误差 (PX4 实际位置 vs ego 命令位置), 收敛窗口后统计
用法: mission_ego_track.py <metrics_out.json> [height=2.0] [track_s=60] [ns=]
"""
import json
import math
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleCommand, VehicleLocalPosition, VehicleCommandAck
from quadrotor_msgs.msg import PositionCommand
from mission_core import OffboardMission

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)


def main():
    out = sys.argv[1]
    kv = dict(x.split("=", 1) for x in sys.argv[2:] if "=" in x)
    height = float(kv.get("height", 2.0))       # 起飞悬停高度
    track_s = float(kv.get("track_s", 60))      # 跟随时长
    converge_s = float(kv.get("converge_s", 8)) # 收敛窗口(不计入统计)
    ego_hz_min = float(kv.get("ego_hz_min", 30))  # ego 命令流最低频率

    rclpy.init()
    m = OffboardMission("ego_tracker")
    m.height = height

    ego = {"pos": None, "vel": None, "acc": None, "yaw": 0.0, "count": 0, "t": 0.0}

    def on_ego(msg):
        ego["pos"] = (msg.position.x, msg.position.y, msg.position.z)
        ego["vel"] = (msg.velocity.x, msg.velocity.y, msg.velocity.z)
        ego["acc"] = (msg.acceleration.x, msg.acceleration.y, msg.acceleration.z)
        ego["yaw"] = msg.yaw
        ego["count"] += 1
        ego["t"] = time.time()

    m.create_subscription(PositionCommand, "/drone_0_planning/pos_cmd", on_ego, QOS)

    # PREFLIGHT: 自身位置有效
    deadline = time.time() + 60
    while time.time() < deadline and not (m.pos and m.pos.xy_valid and m.pos.z_valid):
        rclpy.spin_once(m, timeout_sec=0.5)
    if not m.pos:
        print("MISSION_FAILED no_local_position"); return 1
    time.sleep(8)
    m.metrics["events"].append({"t": m.t(), "e": "preflight_done"})

    # 等 ego 命令流活跃
    deadline = time.time() + 30
    while time.time() < deadline and ego["pos"] is None:
        rclpy.spin_once(m, timeout_sec=0.2)
    if ego["pos"] is None:
        m.land_and_finish(out, height); print("MISSION_FAILED no_ego_stream"); return 1
    m.metrics["events"].append({"t": m.t(), "e": "ego_stream_live"})
    print(f"ego 命令流活跃, 首条命令 ({ego['pos'][0]:.2f}, {ego['pos'][1]:.2f}, {ego['pos'][2]:.2f})")

    # 轨迹重定基: 以 ego 首条命令为原点, 消除框架偏移 (纯跟踪质量度量)
    origin = ego["pos"]
    m.metrics["ego_origin_enu"] = [round(origin[0],3), round(origin[1],3), round(origin[2],3)]
    m.metrics["events"].append({"t": m.t(), "e": "ego_rebase_done"})

    # 起飞+切入: 以重定基后的当前命令(≈原点)为初始设定点
    sp0 = (ego["pos"][0]-origin[0], ego["pos"][1]-origin[1])
    ok = m.arm_and_engage(sp0, height)
    if not ok:
        m.land_and_finish(out, height); print("MISSION_FAILED engage"); return 1
    m.metrics["events"].append({"t": m.t(), "e": "tracking_start"})

    # 跟随环: 命令 = ego pos_cmd (ENU→NED 映射在 heartbeat 内完成), 带 vel/acc 前馈
    errs, errs_conv, csv = [], [], ["t,px,py,pz,ex,ey,ez,err"]
    conv_cnt, conv_started = 0, False
    t0 = time.time()
    end = t0 + track_s
    while time.time() < end and rclpy.ok():
        if ego["pos"] is None:
            rclpy.spin_once(m, timeout_sec=0.05); continue
        ex = ego["pos"][0] - origin[0]   # 重定基: ego 世界 -> PX4 帧
        ey = ego["pos"][1] - origin[1]
        ez = ego["pos"][2]
        m.heartbeat((ex, ey, ez), vel=ego["vel"], acc=ego["acc"])
        rclpy.spin_once(m, timeout_sec=0.02)
        if m.pos:
            px, py, pz = m.pos.x, m.pos.y, m.pos.z
            err = math.sqrt((px-ex)**2 + (py-ey)**2 + (pz+ez)**2)  # pz=NED(z向下), ez=ENU(z向上): 实际高度=pz+ez
            el = time.time() - t0
            errs.append(err)
            csv.append(f"{el:.2f},{px:.3f},{py:.3f},{pz:.3f},{ex:.3f},{ey:.3f},{ez:.3f},{err:.3f}")
            # 距离门限收敛: 误差持续 <1.0m 后才开始统计 (纯跟踪质量)
            if err < 1.0:
                conv_cnt = conv_cnt + 1 if conv_cnt else 1
            else:
                conv_cnt = 0
            if conv_cnt >= 25 and not conv_started:
                conv_started = True
                m.metrics["events"].append({"t": m.t(), "e": "converged"})
            if conv_started:
                errs_conv.append(err)
        time.sleep(0.02)

    m.metrics["tracking"] = {
        "samples": len(errs),
        "converge_s": converge_s,
        "err_mean_m": round(sum(errs_conv)/len(errs_conv), 3) if errs_conv else None,
        "err_max_m": round(max(errs_conv), 3) if errs_conv else None,
        "err_p95_m": round(sorted(errs_conv)[int(len(errs_conv)*0.95)], 3) if len(errs_conv) > 10 else None,
    }
    m.metrics["events"].append({"t": m.t(), "e": "tracking_done"})
    m.land_and_finish(out, height)
    with open(out.replace(".json", "_track.csv"), "w") as f:
        f.write("\n".join(csv))
    print(f"MISSION_DONE {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
