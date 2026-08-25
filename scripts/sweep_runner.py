#!/usr/bin/env python3
"""sweep_runner.py — 网格扫参执行器。用法: sweep_runner.py <spec.yaml>"""
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parent.parent


def main():
    spec_path = Path(sys.argv[1]).resolve()
    spec = yaml.safe_load(spec_path.read_text())
    name = spec["sweep_name"]; mission = spec["mission"]
    base = spec.get("base", {}); grid = spec.get("grid", {}); seeds = spec.get("seeds") or [None]

    keys = sorted(grid.keys())
    combos = list(itertools.product(*(grid[k] for k in keys)))
    total = len(combos) * len(seeds)
    print(f"[sweep:{name}] 组合数={len(combos)} x seeds={len(seeds)} = {total} 次运行")
    print("[sweep] 前置: 确保仿真栈就绪(幂等)...")
    pre = subprocess.run(["./scripts/sim_launch.sh", "--headless"], cwd=WF,
                         capture_output=True, text=True, timeout=480)
    if "READY" not in pre.stdout:
        print("SWEEP_ABORTED stack not ready"); return 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    sweep_dir = WF / "experiments" / f"{stamp}-{mission}-sweep-{name}"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    (sweep_dir / "spec.yaml").write_text(yaml.safe_dump(spec, allow_unicode=True))
    results = []

    for ci, combo in enumerate(combos):
        cell = dict(zip(keys, combo))
        for seed in seeds:
            tag = "_".join(f"{k}={v}" for k, v in cell.items()) + (f"_seed{seed}" if seed is not None else "")
            run_id = f"{stamp}-{mission}-sweep-{name}/runs/{tag}"
            overrides = [f"{k}={v}" for k, v in {**base, **cell}.items()]
            env = {"PROPOSAL_ID": str(spec.get("proposal_id") or ""),
                   "GAP_CELL_ID": str(spec.get("gap_cell_id") or ""),
                   "HYPOTHESIS": str(spec.get("hypothesis") or ""),
                   "SEED": str(seed) if seed is not None else ""}
            print(f"[{ci+1}/{len(combos)}] {tag} ...", flush=True)
            t0 = time.time()
            r = subprocess.run(["./scripts/run_mission.sh", mission, run_id, *overrides],
                               cwd=WF, capture_output=True, text=True,
                               env={**__import__("os").environ, **{k: v for k, v in env.items() if v}})
            ok = "MISSION_DONE" in r.stdout
            results.append({"tag": tag, **cell, "seed": seed, "outcome": "done" if ok else "failed",
                            "rc": r.returncode, "dur_s": round(time.time() - t0, 1)})
            print(f"    -> {results[-1]['outcome']} ({results[-1]['dur_s']}s)")

    (sweep_dir / "sweep_results.json").write_text(json.dumps(results, indent=2))
    fails = sum(1 for r in results if r["outcome"] == "failed")
    print(f"SWEEP_DONE {sweep_dir}  ({len(results)-fails}/{len(results)} ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
