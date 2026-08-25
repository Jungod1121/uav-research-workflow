# UAV Research Workflow — 半自动科研助手

**主体是现有 agent harness（Claude Code / opencode），不是新建科研 agent。**
所有能力以声明式资产存在：SKILL.md（方法论）+ MCP servers（感知/行动通道）+ bash 脚本（原子工具）。换 harness 或升级模型，资产原样可用。

> **状态：已验收（2026-08-25）**。方框任务端到端闭环跑通：
> 一句话触发 → 仿真栈启动 → offboard 飞方框 → rosbag+截图采集 → 观察包 → 诊断报告。
> 验证记录：`experiments/20260825-131734-square/`、`experiments/20260825-134646-square-gui/`

## 全景

```
选题(Atlas已有) → 论证 → 实验 ⇄ 分析(闭环) → 结果产出 → 论文写作 → 投稿
                 gap-to-proposal  run-experiment   obs_pack    vendor skills  deadline_watch
                 gap-watch        iterate-experiment analyze-results(nature-skills×8)
```

## 环境基线（已装好并钉版）

| 组件 | 版本 | 备注 |
|---|---|---|
| Ubuntu / ROS 2 | 22.04 / Humble | 本机原生 |
| Gazebo / PX4 | Harmonic 8.15 / v1.16.0 | server 恒 HEADLESS，GUI 客户端分离 |
| uXRCE-DDS Agent | 静态链接本地构建 | `~/Micro-XRCE-DDS-Agent/build/` |
| MCP: mcp-rosbags | rosbags==0.9.23, mcp==1.12.4 | 15 tools，bag 离线分析 |
| MCP: ros-mcp | mcp==1.9.4（Humble CI 版） | 24 tools，实时话题/服务/仿真控制 |

⚠️ 升级任何依赖前先跑 `docs/WORKFLOW.md` §MCP 的冒烟测试。已知坑（NVIDIA GLX、
lockstep、QoS、版本化话题名等 12 条）全部记录在 `skills/experiment-setup/SKILL.md`。

## 快速开始

```bash
./scripts/sim_launch.sh        # 起仿真栈（幂等，READY 探测；GUI 自动带 GL 兜底）
./scripts/sim_stop.sh          # 干净关停
```

然后对 agent 说：

| 你说 | 触发 |
|---|---|
| 「跑一次方框实验」 | run-experiment → bag+截图+metrics |
| 「分析这次结果」 | analyze-results → diagnosis_report.md |
| 「继续迭代，最多 5 轮」 | iterate-experiment（gate 后汇总） |
| 「VLA × GPS-denied 有变化吗」 | gap-watch（需 Atlas 后端在 8000 端口） |
| 「把这个格子转成开题报告」 | gap-to-proposal |
| 「标注 part_03」 | paper-annotation |
| 「投稿截止日」 | deadline_watch.py |

## 目录

```
skills/    7 个自建技能（已 symlink 到 ~/.claude/skills/）
scripts/   原子工具 + systemd timer 模板
templates/ experiment_log / diagnosis_report / repro_checklist
config/    gap_watchlist.yaml
experiments/  每次实验一个目录（bags/views/logs/metrics.json/diagnosis_report.md）
proposals/    开题产物
vendor/       外部 skills 安装区（当前仅文档化，见 WORKFLOW.md）
docs/WORKFLOW.md  详细手册（MCP 钉版、nature-skills 精选 8 个、Zotero 桥接）
```

## 待启用（一次性）

```bash
systemctl --user enable --now uav-gap-watch.timer   # 每日 gap 追踪
python3 scripts/gap_watch.py --init                  # 建基线快照
```

## 相关仓库

- **UAV Research Atlas**（选题）：`~/work/uav-research-atlas` — 本工作流通过其 HTTP API 只读调用
- 实验工作区即本仓库 `experiments/` 目录（git 忽略大文件，备份走 `backup.sh`）
