---
name: gap-watch
description: 监控 Atlas 中关注的 gap cell 数量变化：定时对比快照，论文数变化≥阈值时提醒（如 VLA×GPS-denied 从1篇变4篇=窗口可能关闭）。触发词：检查gap变化、watchlist、空白还在吗、监控格子。
---

# Gap Watch — 空白格子持续追踪

目的：Atlas 是被动查询工具；本 skill 让关键格子的变化主动找你。核心判断——**窗口期信号**：某格子论文数短期明显上升（尤其成因是 emerging_too_new 时），说明竞争者在涌入。

## Watchlist 定义

编辑 `~/work/uav-research-workflow/config/gap_watchlist.yaml`：

```yaml
cells:
  - name: VLA_x_GPS-denied
    axis_a: {axis: method, node: VLA}
    axis_b: {axis: environment, node: GPS-denied}
    alert_threshold: 2      # 新增论文数 ≥ 此值则提醒
  - name: RL_x_DynamicObstacle
    axis_a: {axis: method, node: Reinforcement Learning}
    axis_b: {axis: environment, node: Dynamic obstacle avoidance}
    alert_threshold: 3
```

## 快照与对比

```bash
# 手动执行一次（也可由 systemd timer 每日调用）
python3 ~/work/uav-research-workflow/scripts/gap_watch.py            # diff + 输出报告
python3 .../gap_watch.py --init                                      # 首次建快照
```

- 脚本行为：读 watchlist → 调 Atlas `GET /api/gap/{a}/{b}` 取当前计数 → 与 `state/gap_snapshots.json` 对比 → 更新快照 → 有越阈变化时输出提醒块；
- 提醒内容：格子名、旧→新计数、近90天增量、成因假设类别、"建议动作"（如：重跑 recompute_gaps 后人工复核新样本论文）。

## 定时化（一次性设置）

```bash
# 用户级 systemd timer，每日 08:30 增量抓取后运行（Atlas ingest 之后）
systemctl --user enable --now uav-gap-watch.timer
```
timer 单元文件在 `scripts/systemd/` 下，`provision.sh` 会安装。日志：`journalctl --user -u uav-gap-watch.service`。

## 判断口径（与 Atlas 一致）

- 计数以 Atlas 分类结果为准（含置信度阈值过滤后的标签）；
- Atlas 全库重分类/阈值调整会导致基数跳变——脚本在检测到全库总量变化 >10% 时自动标注"基数漂移"，该次 diff 不触发提醒；
- 提醒 ≠ 结论：最终判断由用户点开格子详情看新增论文质量。

## 首次使用

1. 确认 Atlas 后端运行中；
2. 编辑 watchlist.yaml 加入你关注的 2–5 个格子（多了会噪音化）;
3. `--init` 建基线快照 → 启用 timer。
