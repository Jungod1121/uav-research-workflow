#!/usr/bin/env python3
"""deadline_watch.py — 机器人/ML 顶会投稿截止日追踪。

数据源（按优先级）:
  1. 内置人工核对的年度周期表（ICRA/RSS/IROS/CoRL/RA-L，历史规律日期，标注"约"）
  2. --fetch 时尝试抓取 aideadlin.es 公开 JSON，成功则合并覆盖（标注"官方"）

用法:
  deadline_watch.py                 # 打印未来 180 天内截止日 Markdown 表
  deadline_watch.py --ics out.ics   # 同时生成日历文件（可导入系统日历）
"""
import argparse
import datetime as dt
import json
import urllib.request

# 历史周期（月-日），年份为下一届；提交前务必以官网为准
BASE = [
    # (name, (month, day), cycle_note, url)
    ("ICRA",   (9, 15), "每年9月中旬", "https://2027.ieee-icra.org/"),
    ("IROS",   (3, 1),  "每年3月初",   "https://www.iros.org/"),
    ("RSS",    (1, 15), "每年1月中下旬", "https://roboticsconference.org/"),
    ("CoRL",   (4, 30), "每年春末(有浮动)", "https://www.corl.org/"),
    ("RA-L",   None,    "滚动投稿, 随时可投", "https://www.ieee-ras.org/publications/ra-l"),
]


def upcoming(years=3):
    today = dt.date.today()
    rows = []
    for name, md, note, url in BASE:
        if md is None:
            rows.append((name, None, note, url)); continue
        for y in range(today.year, today.year + years):
            d = dt.date(y, *md)
            if d >= today:
                rows.append((name, d, note, url))
                break
        else:
            rows.append((name, None, f"{note}(今年已过)", url))
    return sorted([r for r in rows if r[1]], key=lambda x: x[1]) + \
           [r for r in rows if not r[1]]


def try_fetch_aideadlines():
    """可选：从 aideadlin.es 抓 robotics 相关条目。失败静默返回 []。"""
    try:
        req = urllib.request.Request(
            "https://aideadlin.es/?get=all", headers={"User-Agent": "uav-workflow"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        keys = ("ICRA", "IROS", "RSS", "CoRL")
        out = []
        for e in data:
            title = e.get("title", "").upper()
            if any(k in title for k in keys) and e.get("deadline"):
                out.append((e["title"], e["deadline"], "official",
                            e.get("site") or ""))
        return out
    except Exception:
        return []


def write_ics(path, rows):
    def fmt(d):
        return d.strftime("%Y%m%d")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//uav-workflow//deadline//CN"]
    for name, d, note, url in rows:
        if not d:
            continue
        lines += ["BEGIN:VEVENT", f"UID:{name}-{fmt(d)}@uav-workflow",
                  f"DTSTAMP:{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTSTART;VALUE=DATE:{fmt(d)}",
                  f"SUMMARY:{name} 截稿({note})",
                  f"DESCRIPTION:{url}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ics", type=str, default="")
    ap.add_argument("--days", type=int, default=180)
    args = ap.parse_args()

    fetched = try_fetch_aideadlines()
    local = upcoming()
    horizon = dt.date.today() + dt.timedelta(days=args.days)

    print(f"# 投稿截止日（今天 {dt.date.today()}，窗口 {args.days} 天内）\n")
    print("| 会议 | 截止 | 来源 | 备注 |")
    print("|---|---|---|---|")

    seen = set()
    for name, d, note, url in fetched:
        try:
            dd = dt.date.fromisoformat(d[:10])
        except Exception:
            continue
        if dd <= horizon:
            print(f"| **{name}** | {dd} | 官方(aideadlin.es) | [link]({url}) |")
            seen.add(name.split()[0])
    for name, d, note, url in local:
        tag = "" if d and d <= horizon else "(超出窗口)"
        src = "官网核对后更新此表" if name not in seen else ""
        ds = d.isoformat() if d else "-"
        print(f"| {name} | {ds} {tag} | 内置周期表({note}) | {src} [link]({url}) |")

    print("\n> ⚠️ 内置表为历史周期推算（标'约'）；投稿前务必打开官网确认。"
          "\n> 提示: ICRA 通常 9 月中旬截稿——9 月是论文冲刺期。")

    if args.ics:
        from pathlib import Path
        rows = []
        for name, d, note, url in fetched:
            try:
                rows.append((name, dt.date.fromisoformat(d[:10]), note, url))
            except Exception:
                continue
        write_ics(Path(args.ics), rows or local)
        print(f"\nICS written: {args.ics}")


if __name__ == "__main__":
    main()
