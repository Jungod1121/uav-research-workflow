#!/usr/bin/env python3
"""gap_watch.py — 对比 gap_watchlist 中格子的论文计数快照，越阈变化输出提醒。

用法:
  gap_watch.py --init     # 首次建基线（只存不报）
  gap_watch.py            # 常规 diff
  gap_watch.py --json     # 输出 JSON（供其他工具消费）
依赖: 仅标准库。Atlas 后端需运行于 http://localhost:8000
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

WF = Path(__file__).resolve().parent.parent
WATCHLIST = WF / "config" / "gap_watchlist.yaml"
STATE = WF / "state" / "gap_snapshots.json"
ATLAS = "http://localhost:8000"


def load_watchlist():
    """极简 YAML 解析（仅支持本 watchlist 的两层级结构），避免强依赖 PyYAML。"""
    if not WATCHLIST.exists():
        print(f"ERROR: {WATCHLIST} 不存在，参考 skills/gap-watch/SKILL.md 创建"); sys.exit(1)
    cells, cur = [], None
    for raw in WATCHLIST.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        s = line.strip()
        if s.startswith("- name:"):
            cur = {"name": s.split(":", 1)[1].strip()}
            cells.append(cur)
        elif cur is not None and ":" in s:
            k, v = (x.strip() for x in s.split(":", 1))
            if k == "axis_a" or k == "axis_b":
                cur[k] = {}          # 子块由下面 axis/node 行填充
            elif s.startswith(("axis:", "node:")):
                target = cur.get("axis_a") if cur.get("axis_a") is not None else None
                # 判断当前属于 a 还是 b：a 已有两个 key 则写入 b
                tgt = "axis_b" if len(cur.get("axis_a", {}) or {}) >= 2 and "node" in (cur.get("axis_a") or {}) else "axis_a"
                if cur.get("axis_a") and "axis" in cur["axis_a"] and "node" in cur["axis_a"]:
                    tgt = "axis_b"
                cur.setdefault(tgt, {})[k] = v
            elif k == "alert_threshold":
                cur[k] = int(v)
    return [c for c in cells if c.get("name")]


def taxonomy_index():
    with urllib.request.urlopen(f"{ATLAS}/api/taxonomy", timeout=15) as r:
        data = json.loads(r.read())
    idx = {}

    def walk(nodes):
        for n in nodes or []:
            idx[n["label"].lower()] = n["id"]
            walk(n.get("children"))
    if isinstance(data, dict):
        for axis, nodes in data.items():
            walk(nodes)
    else:
        walk(data)
    return idx


def cell_count(cell, tax_idx):
    a = tax_idx.get(cell["axis_a"]["node"].lower())
    b = tax_idx.get(cell["axis_b"]["node"].lower())
    if not a or not b:
        raise KeyError(f"节点找不到 id: {cell['name']}")
    url = f"{ATLAS}/api/gap/{a}/{b}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Atlas 查询失败 {url}: {e}")
    # 兼容不同响应字段命名
    for k in ("count", "observed_count", "n_papers", "total"):
        if isinstance(d, dict) and k in d:
            return int(d[k]), d
    return -1, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cells = load_watchlist()
    prev = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = {"_updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    alerts = []

    tax = taxonomy_index()
    for c in cells:
        cnt, raw = cell_count(c, tax)
        old = prev.get(c["name"], {}).get("count")
        now[c["name"]] = {"count": cnt, "at": now["_updated"]}
        delta = None if old is None else cnt - old
        thr = c.get("alert_threshold", 2)
        hit = (delta is not None and delta >= thr)
        entry = {"cell": c["name"], "old": old, "new": cnt, "delta": delta,
                 "threshold": thr, "alert": bool(hit)}
        alerts.append(entry)
        if args.json:
            continue
        mark = "⚠️ ALERT" if hit else ("  ok   " if delta is not None else "  init ")
        print(f"[{mark}] {c['name']}: {old} -> {cnt} (Δ{delta})")

    if not args.init and prev:
        drift = sum(a["new"] for a in alerts) / max(1, sum(p.get("count", 0) for p in prev.values()
                                                           if isinstance(p, dict)))
        if drift > 0.10:
            print("NOTE: 全库总量变化>10%，本次为基数漂移，提醒已抑制")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(now, indent=2, ensure_ascii=False))

    if args.json:
        print(json.dumps(alerts, ensure_ascii=False, indent=2))
    elif any(a["alert"] for a in alerts) and not args.init:
        print("\n=== GAP ALERT ===")
        for a in alerts:
            if a["alert"]:
                print(f"- {a['cell']}: {a['old']}→{a['new']} 篇 (+{a['delta']}≥{a['threshold']})")
                print("  建议: 打开格子详情复核新增论文；若成因=emerging_too_new，评估窗口剩余时间")
    elif not args.json:
        print("无越阈变化")


if __name__ == "__main__":
    main()
