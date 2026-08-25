#!/usr/bin/env python3
"""edge_metric.py — 定量提取左边线外飘: 轨迹 min(x)。用法: edge_metric.py <exp_dir>"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from obs_pack import find_bag, read_bag_trajectory
exp = Path(sys.argv[1])
bp = find_bag(exp / "bags", "flight")
if not bp: print("METRIC FAILED no_bag"); sys.exit(1)
traj, err = read_bag_trajectory(bp)
if not traj: print(f"METRIC FAILED {err}"); sys.exit(1)
minx = min(p[1] for p in traj)
out = {"left_overshoot_m": round(abs(min(0.0, minx)), 3), "min_x": round(minx, 3)}
(exp / "edge_metric.json").write_text(json.dumps(out))
print(f"METRIC {json.dumps(out)}")
