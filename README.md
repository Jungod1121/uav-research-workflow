# UAV Research Workflow — 半自动科研助手

**主体是现有 agent harness（Claude Code / opencode），不是新建科研 agent。**
所有能力以声明式资产存在：SKILL.md（方法论）+ MCP servers（感知/行动通道）+ bash 脚本（原子工具）。换 harness 或升级模型，资产原样可用。

## 全景

```
选题(Atlas已有) → 论证 → 实验 ⇄ 分析(闭环) → 结果产出 → 论文写作 → 投稿
                 gap-to-proposal  run-experiment   obs_pack    vendor skills  deadline_watch
                 gap-watch        iterate-experiment analyze-results(nature-skills×8)
```

## 快速开始

```bash
./scripts/provision.sh --skip-px4   # 轻量部分(~5min): skills链接+timer+python依赖
./scripts/provision.sh              # 全量: 再加 Gazebo Harmonic + PX4 v1.16 栈(30~60min)
```

然后对 agent 说：

| 你说 | 触发 |
|---|---|
| 「VLA × GPS-denied 这个格子最近有变化吗」 | gap-watch |
| 「把这个格子转成开题报告」 | gap-to-proposal |
| 「跑一次方框实验」 | run-experiment |
| 「分析这次结果」 | analyze-results |
| 「继续迭代，最多5轮」 | iterate-experiment |
| 「标注 part_03」 | paper-annotation |

## 首个闭环验收（MVP）

一句话触发 → `sim_launch.sh --headless` READY → 方框航点 + rosbag + 截图 → `obs_pack.py` 观察包 → `analyze-results` 诊断报告。详见 `docs/WORKFLOW.md`。

## 目录

```
skills/    7 个自建技能（已 symlink 到 ~/.claude/skills/）
scripts/   原子工具：sim_launch/stop、run_mission、capture_view、obs_pack、
           gap_watch、deadline_watch、provision、backup (+systemd/)
templates/ experiment_log / diagnosis_report / repro_checklist
config/    gap_watchlist.yaml
experiments/  每次实验一个目录（bags/views/logs/metrics.json）
proposals/    开题产物（proposal.md + baselines.md + refs.bib）
vendor/       外部 skills 安装区（见 WORKFLOW.md；当前仅文档化）
docs/WORKFLOW.md  详细手册
```

## 相关仓库

- **UAV Research Atlas**（选题）：`~/work/uav-research-atlas` — 本工作流通过其 HTTP API 只读调用
- 实验工作区即本仓库 `experiments/` 目录（独立 git 管理）
