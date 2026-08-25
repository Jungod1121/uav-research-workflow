---
name: run-sweep
description: 结构化参数扫参/消融矩阵：输入参数网格 spec，穷举执行所有组合（单格失败隔离），聚合为 CSV+对比表+多配置轨迹图，直接可进论文。与 iterate-experiment(诊断驱动重试)互补。触发词：扫参、sweep、消融、ablation、参数矩阵、跑一组对比。
---

# Run Sweep — 网格扫参（论文级数据采集）

与 `iterate-experiment` 的边界：**sweep 是穷举**（组合事先定死，为论文表格服务），
iterate 是自适应重试（为调通服务）。论文数据一律走本 skill。

## 输入：网格 spec（templates/sweep_spec.md）

```yaml
sweep_name: speed_tolerance
mission: square
base: {side: 3.0, height: 2.5}          # 固定不变的基线配置
grid:
  speed: [0.6, 1.2]
  wp_tol: [0.2, 0.35]
seeds: [null]                            # 经典控制仿真留 null; RL 阶段填种子列表
hypothesis: "速度与容差对转角超调的独立影响"
gap_cell_id: null                        # 可选, 关联 Atlas 格子
proposal_id: null                        # 可选, 关联开题
```

组合数 = ∏(每个 grid 参数的取值数) × len(seeds)。执行前**必须向用户确认组合总数与预计耗时**（单次任务时长 × 组合数）。

## 执行

```bash
python3 scripts/sweep_runner.py <spec.yaml>
```

- 目录契约：`experiments/{date}-{mission}-sweep-{sweep_name}/` 下每个组合一个 `runs/{组合键}/`（内含完整 bag/metrics/metadata.json，血缘字段继承 spec）；
- **失败隔离**：单格失败记录 `outcome=failed` 后继续下一格，绝不中断整轮；
- 顺序执行（本机单仿真实例，勿并行——DDS/GZ 资源冲突）。

## 聚合

```bash
python3 scripts/sweep_aggregate.py experiments/...-sweep-{name}
```

产出（写入 sweep 目录）：
- `summary.csv` — 每行一个组合：全部 grid 参数 + 到达率/平均误差/任务时长/outcome
- `summary.md` — markdown 表（论文表格的直接底稿）
- `traj_compare.png` — 各组合轨迹叠加对比图

## 诚实性约定

- 每格 metadata.json 独立完整（复用 exp_metadata schema），聚合只读不改；
- 组合数少（<5）时提示用户"这更像 iterate 而非 sweep"；
- 失败格在 summary 中显式标 failed，禁止静默丢弃。
