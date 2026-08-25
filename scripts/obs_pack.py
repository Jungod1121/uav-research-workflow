#!/usr/bin/env python3
"""obs_pack.py — 把一次实验的产物组装成"观察包"：指标摘要 + 轨迹图 + 截图索引 + 日志摘录。

用法: python3 obs_pack.py experiments/<EXP_ID> [--bag flight]
输出: experiments/<EXP_ID>/obs_pack.md  （供 analyze-results / 多模态模型直接阅读）

依赖: 仅 Python 标准库 + matplotlib(画轨迹图，缺失则跳过并注明)。
     bag 解析优先用 rosbags 库（pip install rosbags），缺失则降级为只引用 metrics.json。
"""
import json
import sys
from pathlib import Path

import argparse


def find_bag(bags_dir: Path, name: str):
    """定位 rosbag2 产物：bags/<name>/ 是目录(内含 *_0.db3 或 *.mcap)，旧版也可能是单文件。"""
    cand_dir = bags_dir / name
    if cand_dir.is_dir():
        for pat in ("*.mcap", "*_0.db3", "*.db3"):
            hits = sorted(cand_dir.glob(pat))
            if hits:
                return hits[0]
    for pat in (f"{name}.mcap", f"{name}_0.db3", f"{name}.db3", "*.mcap", "*_0.db3"):
        hits = sorted(bags_dir.glob(pat))
        if hits:
            return hits[0]
    return None


def load_metrics(exp_dir: Path):
    m = exp_dir / "metrics.json"
    if m.exists():
        return json.loads(m.read_text())
    return None


def _px4_typestore():
    """构造含 px4_msgs 自定义类型的 typestore（从源码 .msg 文件注册）。"""
    from rosbags.typesys import Stores, get_typestore, get_types_from_msg
    store = get_typestore(Stores.ROS2_HUMBLE)
    msg_dirs = [
        Path.home() / "px4_ros2_ws/src/px4_msgs/msg",
        Path("/opt/ros/humble/share/px4_msgs/msg"),
    ]
    add = {}
    for d in msg_dirs:
        if d.is_dir():
            for f in sorted(d.glob("*.msg")):
                try:
                    add.update(get_types_from_msg(f.read_text(), f"px4_msgs/msg/{f.stem}"))
                except Exception:
                    pass
            break
    if add:
        store.register(add)
    return store


def read_bag_trajectory(bag_path: Path):
    """从 mcap/db3 中提取 vehicle_local_position 轨迹 [(t,x,y,z)]。失败返回 None。"""
    try:
        from rosbags.highlevel import AnyReader
    except ImportError:
        return None, "rosbags 库未安装 (pip install rosbags)"
    try:
        target = bag_path.parent if (bag_path.parent / "metadata.yaml").exists() else bag_path
        with AnyReader([target], default_typestore=_px4_typestore()) as reader:
            conns = [c for c in reader.connections if c.topic == "/fmu/out/vehicle_local_position"]
            if not conns:
                return None, "bag 中无 /fmu/out/vehicle_local_position"
            out = []
            for conn, ts, raw in reader.messages(connections=conns):
                msg = reader.deserialize(raw, conn.msgtype)
                t0 = getattr(out[0], "timestamp", None) if out else None
                out.append((ts / 1e9, float(msg.x), float(msg.y), float(msg.z)))
            if out:
                base = out[0][0]
                out = [((a - base), x, y, z) for a, x, y, z in out]
            return out, None
    except Exception as e:  # noqa: BLE001
        return None, f"解析失败: {e}"


def plot_trajectory(traj, out_png: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [p[1] for p in traj]
    ys = [p[2] for p in traj]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(xs, ys, lw=1.2)
    ax.plot(xs[0], ys[0], "g^", label="start")
    ax.plot(xs[-1], ys[-1], "rs", label="end")
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    ax.legend(); ax.set_title("trajectory (vehicle_local_position)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir", type=Path)
    ap.add_argument("--bag", default="flight")
    args = ap.parse_args()
    exp = args.exp_dir.resolve()

    if not exp.exists():
        print(f"ERROR: {exp} 不存在"); return 1

    lines = [f"# OBS_PACK — {exp.name}", ""]
    metrics = load_metrics(exp)

    # ---- 指标摘要 ----
    lines += ["## Metrics", ""]
    if metrics:
        wps = metrics.get("waypoints", [])
        reached = sum(1 for w in wps if w.get("reached"))
        lines.append(f"- 任务参数: side={metrics.get('side')}m height={metrics.get('height')}m "
                     f"speed={metrics.get('speed')}m/s wp_tol={metrics.get('wp_tol')}")
        for w in wps:
            flag = "OK " if w.get("reached") else "MISS"
            lines.append(f"- WP{w['wp']} [{flag}] final_err={w.get('final_err_m')}m @t={w.get('t')}s")
        lines.append(f"- 到达率: {reached}/{len(wps)}")
        evs = {e["event"] for e in metrics.get("events", [])}
        lines.append(f"- 关键事件: {sorted(evs)}")
    else:
        lines.append("- metrics.json 缺失（任务可能未跑完）")

    # ---- 轨迹图 ----
    lines += ["", "## Trajectory", ""]
    bag_path = find_bag(exp / "bags", args.bag)
    traj, err = (None, "未找到 bag 文件") if not bag_path else read_bag_trajectory(bag_path)
    png = exp / "traj_plot.png"
    if traj:
        try:
            plot_trajectory(traj, png)
            lines.append(f"![trajectory](traj_plot.png)")
            zs = [abs(p[3]) for p in traj]
            lines.append(f"- 点数 {len(traj)}; 高度范围 {min(zs):.2f}~{max(zs):.2f}m; "
                         f"时长 {traj[-1][0]:.1f}s")
        except Exception as e:  # noqa: BLE001
            lines.append(f"- 画图失败: {e}")
    else:
        lines.append(f"- 无法生成轨迹图: {err}")

    # ---- 截图索引 ----
    views = sorted((exp / "views").glob("*.png")) if (exp / "views").exists() else []
    lines += ["", f"## Views ({len(views)} frames)", ""]
    if views:
        step = max(1, len(views) // 6)   # 最多内嵌 6 张关键帧
        for v in views[::step]:
            lines.append(f"![{v.name}]({v.relative_to(exp)})")
        if len(views) % step and views[-1] not in views[::step]:
            lines.append(f"![{views[-1].name}]({views[-1].relative_to(exp)})")
    else:
        lines.append("- 无截图（检查 DISPLAY 或 logs/views.log）")

    # ---- 日志摘录 ----
    lines += ["", "## Log digest", ""]
    for lg in ["launch.log", "mission.log"]:
        p = exp / "logs" / lg
        if p.exists():
            content = p.read_text(errors="replace").strip().splitlines()
            tail = content[-15:] if len(content) > 15 else content
            lines += [f"<details><summary>{lg}</summary>", "", "```",
                      *tail, "```", ""]

    out = exp / "obs_pack.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OBS_PACK_READY {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
