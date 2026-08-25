#!/usr/bin/env python3
"""exp_metadata.py — 实验血缘 schema: metadata.json 的生成与读取。

字段契约(全工作流共享, 改动需同步 exp_index.py / sweep_aggregate.py):
  exp_id, timestamp, mission, hostname,
  proposal_id?, gap_cell_id?, hypothesis?, parent_experiment_id?, iteration_round?,
  resolved_config{}, config_hash, seed?,
  git{workflow, px4}, stack{px4, gz, ros}

用法:
  exp_metadata.py write <exp_dir> <mission> [--proposal ID] [--gap-cell ID]
                        [--hypothesis TXT] [--parent EXP_ID] [--round N] [--seed N]
                        [--config k=v ...]
  exp_metadata.py read <exp_dir>
"""
import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

WF = Path(__file__).resolve().parent.parent


def _git(dirpath, args=("rev-parse", "--short", "HEAD")):
    try:
        return subprocess.run(["git", "-C", str(dirpath), *args],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None


def collect(mission, overrides, **link):
    px4_dir = Path.home() / "PX4-Autopilot"
    resolved = dict(o.split("=", 1) for o in overrides)
    cfg_json = json.dumps(resolved, sort_keys=True)
    meta = {
        "exp_id": Path(link["exp_dir"]).name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mission": mission,
        "hostname": socket.gethostname(),
        "proposal_id": link.get("proposal_id"),
        "gap_cell_id": link.get("gap_cell_id"),
        "hypothesis": link.get("hypothesis"),
        "parent_experiment_id": link.get("parent"),
        "iteration_round": link.get("round"),
        "seed": link.get("seed"),
        "resolved_config": resolved,
        "config_hash": hashlib.sha256(cfg_json.encode()).hexdigest()[:12],
        "git": {"workflow": _git(WF), "px4": _git(px4_dir)},
        "stack": {"px4": "v1.16.0", "gz": "harmonic", "ros": "humble"},
    }
    return meta


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("exp_dir")
    w.add_argument("mission")
    w.add_argument("--proposal"); w.add_argument("--gap-cell")
    w.add_argument("--hypothesis"); w.add_argument("--parent")
    w.add_argument("--round", type=int); w.add_argument("--seed", type=int)
    w.add_argument("--config", nargs="*", default=[])
    r = sub.add_parser("read"); r.add_argument("exp_dir")
    a = ap.parse_args()

    exp_dir = Path(a.exp_dir).resolve()
    if a.cmd == "read":
        p = exp_dir / "metadata.json"
        print(p.read_text() if p.exists() else f"NO_METADATA {p}")
        return 0
    meta = collect(a.mission, a.config, exp_dir=str(exp_dir), proposal_id=a.proposal,
                   gap_cell_id=a.gap_cell, hypothesis=a.hypothesis, parent=a.parent,
                   round=a.round, seed=a.seed)
    (exp_dir / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"META_OK {exp_dir/'metadata.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
