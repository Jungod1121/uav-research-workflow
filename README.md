# UAV Research Workflow — 半自动科研助手

**主体是现有 agent harness（Claude Code / opencode），不是新建科研 agent。**
所有能力以声明式资产存在：SKILL.md（方法论）+ MCP servers（感知/行动通道）+ bash 脚本（原子工具）。换 harness 或升级模型，资产原样可用。

> **状态：v2.1 已验收（2026-08-26）**。
> 单机 HOLD 漂移 0.068m → 方框四分点 0.104m（&lt;0.15m 达标）→ 双机 bring-up（0.068/0.105m）→ 编队飞行（Leader 13/13 + Follower 跟随）→ Docker 镜像 `uav-sim:humble` 容器内全链路复现。
> 监控台 `http://localhost:8765` 实时聚合构建/仿真/实验/系统。

## 全景

```
选题(Atlas已有) → 论证 → 实验 ⇄ 分析(闭环) → 结果产出 → 论文写作 → 投稿
                 gap-to-proposal  run-experiment   obs_pack    vendor skills  deadline_watch
                 gap-watch        iterate-experiment analyze-results(nature-skills×8)
                                 run-sweep        sweep_aggregate
                                 mission_core(状态机)
```

七层系统视图（对应"机器人不动"分类学）：`PX4 SITL → Gazebo → MAVROS/uXRCE → Python ROS 节点 → 任务状态机 → 控制/规划 → 无人机`

## 环境基线（已装好并钉版）

| 组件 | 版本 | 备注 |
|---|---|---|
| Ubuntu / ROS 2 | 22.04 / Humble | 本机原生 |
| Gazebo / PX4 | Harmonic 8.15 / v1.16.0 | server 恒 HEADLESS，`px4-rc.params` 三件套（COM_RC_IN_MODE=4, RCL_EXCEPT=4, NAV_DLL_ACT=0） |
| uXRCE-DDS Agent | 静态链接本地构建 | `~/Micro-XRCE-DDS-Agent/build/`，单 agent 多客户端 |
| MCP: mcp-rosbags | rosbags==0.9.23, mcp==1.12.4 | 15 tools，bag 离线分析 |
| MCP: ros-mcp | mcp==1.9.4（Humble CI 版） | 24 tools，实时话题/服务/仿真控制 |
| Docker | 29.1.3 + 镜像 `uav-sim:humble` 11.4GB | `ros:humble` 基镜像 + gz-harmonic + PX4 v1.16.0 编译产物 |
| 监控台 | FastAPI + Tailwind | `http://localhost:8765`，`uav-monitor.service` 自启动 |

## 快速开始

### 原生仿真栈

```bash
./scripts/sim_launch.sh        # 起仿真栈（幂等，READY 探测；GUI 自动带 GL 兜底）
./scripts/sim_stop.sh          # 干净关停
# 双机：STACK_INSTANCES=2 ./scripts/sim_launch.sh
```

### 监控台

```bash
systemctl --user status uav-monitor.service   # 已自启动
# 浏览器打开 http://localhost:8765
# 聚合：docker-build 进度 / sim 日志 / ros hz / experiments 血缘表 / system 指标
```

### Docker 可复现层（别人一条命令）

```bash
# 宿主机需先配代理（Clash 7897）：
# /etc/systemd/system/docker.service.d/proxy.conf 已配好
sg docker -c "docker run -d --name uav-sim --network host --shm-size 2gb -e ROS_DOMAIN_ID=77 -e STACK_INSTANCES=1 uav-sim:humble"
# 容器内验证：
sg docker -c "docker exec uav-sim bash -c 'source /opt/ros/humble/setup.bash && source /root/px4_ros2_ws/install/setup.bash && timeout 8 ros2 topic hz /fmu/out/sensor_combined --window 8'"
# 容器内任务（血缘同原生）：
sg docker -c "docker exec uav-sim bash -c 'source /opt/ros/humble/setup.bash && source /root/px4_ros2_ws/install/setup.bash && timeout 150 python3 scripts/run_mission_v2.py hold /tmp/h.json'"
```

### 对 agent 说

| 你说 | 触发 |
|---|---|
| 「跑一次方框实验」 | run-experiment → bag+截图+metrics |
| 「分析这次结果」 | analyze-results → diagnosis_report.md |
| 「继续迭代，最多 5 轮」 | iterate-experiment（gate 后汇总） |
| 「扫参 speed×tol 网格」 | run-sweep → sweep_runner + aggregate（CSV+对比图） |
| 「VLA × GPS-denied 有变化吗」 | gap-watch（需 Atlas 后端在 8000 端口） |
| 「把这个格子转成开题报告」 | gap-to-proposal |
| 「标注 part_03」 | paper-annotation |
| 「投稿截止日」 | deadline_watch.py |

## 目录

```
skills/    7+1 自建技能（run-sweep 新增，已 symlink 到 ~/.claude/skills/）
scripts/   原子工具（mission_core 状态机、run_mission_v2、edge_metric、sweep、smoke_test…）+ systemd timer 模板
launch/    sim_stack.launch.py（声明式编排，STACK_INSTANCES 双机官方约定）
docker/    Dockerfile + compose + px4-src.tar.gz（可复现构建，含 8 项构建坑修复）
webui/     监控台（FastAPI 后端 + Apple 风格前端，8765）
templates/ experiment_log / diagnosis_report / repro_checklist / sweep_spec
config/    gap_watchlist.yaml
experiments/  每次实验一个目录（metadata.json 血缘 + metrics + diagnosis）
proposals/    开题产物
vendor/       外部 skills 安装区（当前仅文档化，见 WORKFLOW.md）
docs/WORKFLOW.md  详细手册（MCP 钉版、nature-skills 精选 8 个、Zotero 桥接、七层视图）
```

## 待启用（一次性）

```bash
systemctl --user enable --now uav-gap-watch.timer   # 每日 gap 追踪
systemctl --user enable --now uav-smoke.timer       # 每周 smoke（9:00 周一）
python3 scripts/gap_watch.py --init                  # 建基线快照
```

## 相关仓库

- **UAV Research Atlas**（选题）：`~/work/uav-research-atlas` — 本工作流通过其 HTTP API 只读调用
- 实验工作区即本仓库 `experiments/` 目录（git 忽略大文件，备份走 `backup.sh`）
