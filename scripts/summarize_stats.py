#!/usr/bin/env python3
"""summarize_stats.py — 汇总 N=10 L2.5 统计运行 → stats_summary.md + CSV
用法: summarize_stats.py <glob 例如 'experiments/v29-iterate/stat-*.json'>
"""
import csv
import glob
import json
import statistics
import sys

files = sorted(glob.glob(sys.argv[1]))
rows = []
for f in files:
    if f.endswith("_track.csv"):
        continue
    d = json.load(open(f))
    t = d.get("tracking", {})
    ev = [e["e"] for e in d.get("events", [])]
    cf = f.replace(".json", "_track.csv")
    xr = (None, None)
    try:
        rr = list(csv.DictReader(open(cf)))
        xs = [float(r["px"]) for r in rr]
        xr = (round(min(xs), 2), round(max(xs), 2))
    except Exception:
        pass
    success = "land_cmd_sent" in ev and t.get("samples", 0) > 100
    rows.append({
        "run": f.split("/")[-1].replace(".json", ""),
        "samples": t.get("samples"),
        "mean": t.get("err_mean_m"),
        "p95": t.get("err_p95_m"),
        "peak": t.get("err_max_m"),
        "x_min": xr[0], "x_max": xr[1],
        "traversed": xr[0] is not None and xr[0] <= -10,
        "success": success,
    })

ok = [r for r in rows if r["traversed"] and r["success"]]
print("| 运行 | 样本 | 均值(m) | P95(m) | 峰值(m) | x范围 | 穿越 | 成功 |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['run']} | {r['samples']} | {r['mean']} | {r['p95']} | {r['peak']} | [{r['x_min']}, {r['x_max']}] | {'✓' if r['traversed'] else '✗'} | {'✓' if r['success'] else '✗'} |")
means = [r["mean"] for r in ok if r["mean"] is not None]
p95s = [r["p95"] for r in ok if r["p95"] is not None]
peaks = [r["peak"] for r in ok if r["peak"] is not None]
if means:
    print(f"\n**统计 (n={len(ok)} 有效)**: 跟踪误差均值 {statistics.mean(means):.3f}±{statistics.stdev(means):.3f} m | "
          f"P95 {statistics.mean(p95s):.3f}±{statistics.stdev(p95s):.3f} m | 峰值最差 {max(peaks):.3f} m | 成功率 {len(ok)}/{len(rows)}")
with open(sys.argv[1].replace("*.json", "summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
