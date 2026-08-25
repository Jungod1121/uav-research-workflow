#!/usr/bin/env python3
"""exp_index.py — 扫描 experiments/, 重建「gap→proposal→实验链」关系表。

用法: python3 exp_index.py [--json]
输出: experiments/INDEX.md (markdown 关系表) + stdout 摘要
"""
import json
import sys
from pathlib import Path

WF = Path(__file__).resolve().parent.parent
EXP = WF / "experiments"


def main():
    rows, no_meta = [], []
    for d in sorted(EXP.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "INDEX.md":
            continue
        mp = d / "metadata.json"
        if not mp.exists():
            no_meta.append(d.name); continue
        m = json.loads(mp.read_text())
        cfg = m.get("resolved_config", {})
        rows.append({
            "exp_id": m["exp_id"],
            "gap_cell": m.get("gap_cell_id") or "—",
            "proposal": m.get("proposal_id") or "—",
            "hypothesis": (m.get("hypothesis") or "—")[:40],
            "parent": m.get("parent_experiment_id") or "—",
            "round": m.get("iteration_round") or "—",
            "config": " ".join(f"{k}={v}" for k, v in cfg.items())[:60] or "—",
            "cfg_hash": m.get("config_hash", "—"),
        })
    lines = ["# Experiment Index — gap→proposal→实验链", "",
             "| exp_id | gap_cell | proposal | hypothesis | parent | round | config | cfg_hash |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| {exp_id} | {gap_cell} | {proposal} | {hypothesis} | {parent} | {round} | `{config}` | {cfg_hash} |".format(**r))
    if no_meta:
        lines += ["", f"## 缺 metadata（历史实验，建议 backfill）", *[f"- {n}" for n in no_meta]]
    out = EXP / "INDEX.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"INDEX_OK {out} ({len(rows)} experiments, {len(no_meta)} missing metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
