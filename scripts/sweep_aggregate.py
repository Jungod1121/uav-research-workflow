#!/usr/bin/env python3
"""sweep_aggregate.py — 聚合 sweep 目录: summary.csv/md + 轨迹对比图。
用法: sweep_aggregate.py experiments/<...-sweep-<name>>"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from obs_pack import find_bag, read_bag_trajectory  # noqa: E402

WF = Path(__file__).resolve().parent.parent


def main():
    sweep_dir = Path(sys.argv[1]).resolve()
    runs = sweep_dir / "runs"
    results = json.loads((sweep_dir / "sweep_results.json").read_text())
    rows = []
    for r in results:
        run_dir = runs / r["tag"]
        row = dict(r)
        mp = run_dir / "metrics.json"
        if mp.exists():
            m = json.loads(mp.read_text())
            wps = m.get("waypoints", [])
            row["reached"] = f"{sum(1 for w in wps if w.get('reached'))}/{len(wps)}"
            errs = [w.get("final_err_m") for w in wps if w.get("final_err_m") is not None]
            row["mean_err"] = round(sum(errs) / len(errs), 3) if errs else None
            row["mission_t"] = (m.get("events") or [{}])[-1].get("t")
        rows.append(row)

    fields = list({k for r in rows for k in r})
    with open(sweep_dir / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted(fields)); w.writeheader(); w.writerows(rows)

    md = ["# Sweep Summary — " + sweep_dir.name, "",
          "| " + " | ".join(sorted(fields)) + " |",
          "|" + "---|" * len(fields)]
    for r in rows:
        md.append("| " + " | ".join(str(r.get(k, "")) for k in sorted(fields)) + " |")
    (sweep_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")

    # 轨迹对比图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 6))
        for r in rows:
            bp = find_bag(runs / r["tag"] / "bags", "flight")
            if not bp:
                continue
            traj, err = read_bag_trajectory(bp)
            if traj:
                ax.plot([p[1] for p in traj], [p[2] for p in traj], lw=1.1, label=r["tag"][:40])
        ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
        ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_title("trajectory comparison")
        fig.tight_layout(); fig.savefig(sweep_dir / "traj_compare.png", dpi=150)
    except Exception as e:  # noqa: BLE001
        print(f"WARN 对比图失败: {e}")

    print(f"AGGREGATE_OK {sweep_dir} (summary.csv/md, traj_compare.png)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
