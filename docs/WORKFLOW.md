# WORKFLOW — 详细手册

> 阶段地图：**选题**(Atlas) → **论证** → **实验** ⇄ **分析** → **结果产出** → **论文写作** → **投稿**
> 设计原则：主体 = 现有 agent harness；能力 = 声明式资产（SKILL.md / MCP / scripts）；无自建编排代码。

---

## 1. 选题阶段（已有 Atlas，两个增强）

### gap-watch（持续追踪）
- 配置：`config/gap_watchlist.yaml`（2–5 个格子）
- 手动：`python3 scripts/gap_watch.py`；首次 `--init`
- 定时：`systemctl --user status uav-gap-watch.timer`（provision 已启用，每日 08:30）
- 口径：Atlas 分类计数；全库重分类导致的基数跳变自动抑制提醒
- 信号解读：emerging_too_new 格子计数快速上升 = 窗口可能在关闭 → 复核新增论文质量后决策

### gap-to-proposal（空白→开题答卷）
- 流程：Atlas API 拉证据 → 归纳 baseline/数据集/指标（**用户确认点**）→ 生成 proposal 骨架 → 文献落 refs.bib / 推 Zotero
- 产出：`proposals/{date}-{slug}/{proposal.md, baselines.md, refs.bib}`

## 2. 实验阶段

### 环境（experiment-setup skill 为准）
钉死组合：Ubuntu22.04 · Humble · gz-harmonic · PX4 v1.16 · uXRCE-DDS v2.4.3。
安装走 `scripts/provision.sh`。已知坑清单在 SKILL.md 内（follow-camera、环境变量残留、msg 版本对齐、ROS_DOMAIN_ID=77…）。

### 单次实验（run-experiment skill 为准）
```
sim_launch.sh [--headless|--no-rviz]   # 幂等启动+READY探测
run_mission.sh square <EXP_ID> [k=v…]  # 任务+bag+截图 时间对齐
sim_stop.sh                            # 干净关停(含进程清理验证)
```
产物目录契约：`experiments/<EXP_ID>/{bags,views,logs,metrics.json}`。

### 半自动闭环（iterate-experiment skill 为准）
诊断 → 改配置(≤2 变量/轮) → 重跑 → 记 iterations.md；gate：连续 N=5 轮 / 目标达成复跑确认 / 连续2轮恶化熔断回滚 → 汇总报告。红线：只改配置不改源码凑指标；历史实验目录永不删除。

## 3. 分析与结果产出

- `obs_pack.py experiments/<EXP_ID>`：指标摘要 + 轨迹图(matplotlib) + 关键帧 + 日志摘录 → `obs_pack.md`
- `analyze-results`：数据通道(bag 结构化) × 视觉通道(直接读图) 双通道交叉 → `diagnosis_report.md`，结论必须挂证据，落到失败分类学 F1–F6
- 图表再生成：所有论文图由脚本从 bag/wandb 重画，禁止手工截图（审稿人改指标时你会感谢这条）

### MCP 通道（助手的眼睛和手）

| Server | 能力 | 安装 |
|---|---|---|
| rosbags-mcp | bag 结构化查询: analyze_trajectory / get_image_at_time / plot_timeseries / tf_tree | 见 §MCP 安装 |
| ros-mcp | 实时 ROS2: 发话题/调服务/控 Gazebo/RViz、进程编排 | 见 §MCP 安装 |

#### §MCP 安装（已接入，2026-08-25 实测）

| Server | 仓库 | 钉版 | 冒烟验证 |
|---|---|---|---|
| mcp-rosbags | `binabik-ai/mcp-rosbags`（论文官方） | venv: `rosbags==0.9.23` + `mcp==1.12.4` | INIT OK, 15 tools |
| ros-mcp | `Yutarop/ros-mcp`（Humble CI） | venv: `mcp==1.9.4` | INIT OK, 24 tools |

> ⚠️ 版本教训：`rosbags≥0.10` 移除了 `deserialize_cdr`；`mcp 2.x` 破坏了 lowlevel API——**升级前先在 venv 里重跑冒烟测试**：
> ```bash
> printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
>   | <server启动命令> | python3 -c "import sys,json; [print(json.loads(l).get('id'), 'OK' if 'result' in json.loads(l) else 'ERR') for l in sys.stdin if l.strip()]"
> ```

配置：本仓库 `.mcp.json` 已写好（Claude Code 项目级自动加载）。opencode 用户把同结构写入 `~/.config/opencode/opencode.json` 的 `mcp` 段。
ros-mcp 的 GUI 类工具（launch_gazebo/launch_rviz）依赖其 socket_server（localhost:8765）在桌面会话中运行；核心 topic/service 工具不依赖。

## 4. 论文写作与投稿（vendor skills，当前仅文档化）

### 主套件 nature-skills（github.com/Yuan1z0825/nature-skills，Apache-2.0）

精选 8 个及定位：

| Skill | 状态 | 用途 | 工作流位置 |
|---|---|---|---|
| nature-figure | Stable | 投稿级科研图（多面板/碰撞审计） | 结果产出 |
| nature-polishing | Stable | Nature 风格润色/术语一致性 | 论文写作 |
| nature-ref-verifier | Stable | 参考文献多源交叉验证 | 论文写作 |
| nature-literature-pipeline | Stable | 每日文献发现推送 | 选题补充 |
| nature-proposal-writer | Beta | proposal-first 写作状态机 | 论证（消费 gap-to-proposal 产物） |
| nature-reviewer | Draft | 三盲 reviewer 模拟 | 投稿前自审 |
| nature-response | Beta | 逐点回复 + cover letter | 修回 |
| nature-reader | Beta | 中英对照精读 reader | 读文献 |

未选：nature-citation（限 CNS 期刊，UAV 方向弱）、paper2ppt/patent 等（按需再加）。

安装（用到时执行一次）：
```bash
mkdir -p ~/ai-skills && git clone https://github.com/Yuan1z0825/nature-skills.git ~/ai-skills/nature-skills
# Claude Code 方式A: subagent wrapper 指向 ~/ai-skills/nature-skills/skills/<name>/SKILL.md（保留完整目录结构！）
# 方式B: scripts/autoupdate-skills.sh --force 直接复制进 ~/.claude/skills/
```

备选套件（nature-skills 不满足时的替代）：WenyuChiou/academic-writing-skills（手稿全生命周期系统）、bahayonghang/academic-writing-skills（latex-paper-en 编译+bib-search）、davila7 scientific-visualization（journal 规格图表）。功能与主套件大量重叠，勿同时装同类。

### LaTeX 工程约定
- IEEEtran 模板（ICRA/IROS 会议版 / RA-L 期刊版两套骨架，开题立项时初始化）
- 引用单一来源：Zotero Better BibTeX 自动导出的 .bib（或 proposals/*/refs.bib），禁止双份维护
- 图表脚本入仓库 `figures/`，数据源标注 wandb run id 或 bag 路径

### 截止日追踪
`python3 scripts/deadline_watch.py [--ics out.ics]`——内置周期表 + aideadlin.es 在线合并。注意 ICRA 约 9 月中旬截稿。

## 5. 基础设施

- **备份** `backup.sh`（restic）：Tier1 代码/db/taxonomy 必备；Tier2 bags/checkpoints 大文件单独 tag；7日/4周/6月保留；外部盘再同步一份（3-2-1）
- **换机恢复**：新机装 ROS2 Humble → `./scripts/provision.sh` → `restic restore`
- **W&B**：训练类实验第一天接入；run id 写进 experiment_log 与 metrics.json，双向可查

## 6. 诚实边界

- 「连续 N 轮」等 gate 是会话约定（我遵守 SKILL.md），非进程级硬保证；无人值守需求出现时再加薄 runner
- 提醒 ≠ 结论：gap-watch 只报变化，判断在人
- AI 不代替选题决策与方法设想（proposal 第 4 章留白给作者）
