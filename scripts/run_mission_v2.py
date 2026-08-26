#!/usr/bin/env python3
"""run_mission_v2.py — mission_core 消费者: hold / square 两种任务定义。
用法: run_mission_v2.py <hold|square> <metrics_out.json> [side=3.0] [height=2.5] [wp_tol=0.35] [hold_s=10] [ns=]
"""
import math
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import rclpy
from mission_core import OffboardMission


def main():
    mission, out = sys.argv[1], sys.argv[2]
    kv = dict(x.split("=", 1) for x in sys.argv[3:] if "=" in x)
    side = float(kv.get("side", 3.0))
    height = float(kv.get("height", 2.5))
    tol = float(kv.get("wp_tol", 0.35))
    hold_s = float(kv.get("hold_s", 10))
    ns = kv.get("ns", "")

    rclpy.init()
    bag = subprocess.Popen(
        ["ros2", "bag", "record", "-o", out.replace(".json", "_bag"),
         "/fmu/out/vehicle_local_position", "/fmu/out/vehicle_attitude",
         "/fmu/out/vehicle_odometry", "/fmu/out/vehicle_status_v1",
         "/fmu/out/vehicle_control_mode", "/fmu/out/sensor_combined"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    m = OffboardMission(f"mission_{mission}", namespace=ns)
    m.height = height

    if not m.preflight():
        m.land_and_finish(out, height); print("MISSION_FAILED preflight"); return 1

    home = (m.pos.x, m.pos.y)
    if mission == "hold":
        ok = m.arm_and_engage(home, height)
        if not ok:
            m.land_and_finish(out, height)
            time.sleep(2); bag.send_signal(signal.SIGINT); bag.wait()
            print("MISSION_FAILED engage"); return 1
        end = time.time() + hold_s
        drift = 0.0
        while time.time() < end:
            m.heartbeat((home[0], home[1], height)); rclpy.spin_once(m, timeout_sec=0.05)
            if m.pos:
                drift = max(drift, math.hypot(m.pos.x - home[0], m.pos.y - home[1]))
        m.metrics["drift_max_m"] = round(drift, 3)
        m.metrics["events"].append({"t": m.t(), "e": "hold_done"})
    elif mission == "square":
        s = side
        wps = [(s/2, 0), (s, 0), (s, s/2), (s, s), (s/2, s), (0, s), (0, s/2), (0, 0)]
        ok = m.arm_and_engage(home, height)
        if not ok:
            m.land_and_finish(out, height)
            time.sleep(2); bag.send_signal(signal.SIGINT); bag.wait()
            print("MISSION_FAILED engage"); return 1
        reached, details = m.fly_waypoints(home, height, wps, wp_tol=tol)
        m.metrics["waypoints"] = details
        m.metrics["reached"] = f"{reached}/{len(wps)}"
    else:
        print(f"MISSION_FAILED unknown mission {mission}"); return 1

    m.land_and_finish(out, height)
    time.sleep(2); bag.send_signal(signal.SIGINT); bag.wait()
    print(f"MISSION_DONE {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
