---
name: run-experiment
description: 编排并执行一次 UAV 仿真实验：启动 PX4 SITL + Gazebo 栈、执行任务（如方框航点）、录制 rosbag、采集指标与画面、干净关停。触发词：跑一次实验、run experiment、飞方框、执行任务、开始录制。
---

# Run Experiment — 单次实验编排

本 skill 是「跑一次实验」的标准流程。执行者是当前 agent（你），通过 bash 调用 `scripts/` 下的原子工具，不做任何即兴发挥；偏离流程时必须在最终报告中说明原因。

## 前置检查（每次必做）

1. 环境就绪检查，任一失败则停止并报告缺失项：
   ```bash
   ls /opt/ros/humble/setup.bash        # ROS2 Humble
   command -v gz                         # Gazebo Harmonic
   ls ~/work/uav-research-workflow/scripts/sim_launch.sh
   ```
2. 残留进程检查（上次实验没清干净会导致 DDS 冲突）：
   ```bash
   pgrep -af "px4|gz sim|ruby|MicroXRCEAgent|rviz2|offboard" || echo clean
   ```
   若有残留 → 先执行 `sim_stop.sh` 清理，确认输出 clean 后再继续。
3. 磁盘余量 < 10GB 时停止，提醒用户先备份/清理 bags。

## 实验定义输入

启动前向用户（或上游 skill）确认四要素，缺省值如下：

| 要素 | 缺省 | 说明 |
|---|---|---|
| 任务 | square（方框航点） | 对应 `scripts/` 内 mission 配置 |
| 配置覆盖 | 无 | Hydra 风格 key=value 列表 |
| **血缘** | 无 | `PROPOSAL_ID`/`GAP_CELL_ID`/`HYPOTHESIS`/`PARENT_EXP`(env 传入)；有开题产物时必填 proposal_id，验证性实验至少给 HYPOTHESIS |
| 录制时长 | 任务自动结束 | 上限 10 分钟保险 |
| 视觉采样 | 每 5s 一帧 | RViz/Gazebo 截图 |

## 执行序列

```bash
cd ~/work/uav-research-workflow

# 1. 生成本次实验 ID 与目录（bag、截图、日志都落这里）
EXP_ID=$(date +%Y%m%d-%H%M%S)-square          # 命名：日期-时间-任务名
mkdir -p experiments/$EXP_ID/{bags,views,logs}

# 2. 启动仿真栈（幂等；内部含清理逻辑）
./scripts/sim_launch.sh --headless 2>&1 | tee experiments/$EXP_ID/logs/launch.log
#    --headless: 只起 gz server + uXRCE agent + rviz2(可选)
#    不加参数则起完整 GUI。等待脚本输出 READY 再进入下一步。

# 3. 执行任务 + 录制（同一脚本内完成，保证时间对齐）
./scripts/run_mission.sh square $EXP_ID ${CONFIG_OVERRIDES:-}
#    成功标志：输出 "MISSION_DONE" 与最终指标 JSON。

# 4. 关停并验证干净
./scripts/sim_stop.sh 2>&1 | tee -a experiments/$EXP_ID/logs/launch.log
pgrep -af "px4|gz sim|MicroXRCEAgent" && echo "WARN: 残留进程见上" || echo "CLEAN_SHUTDOWN"
```

## 产物清单（缺一即在报告中标注 FAILED）

```
experiments/$EXP_ID/
├── bags/flight.db3(.mcap)      # 全话题 rosbag2
├── views/*.png                 # 时间戳命名的截图序列
├── logs/launch.log             # 栈启动/关停日志
├── logs/mission.log            # offboard 节点日志
└── metrics.json                # 结构化指标（起飞耗时/航点误差/总时长…）
```

## 收尾

1. 运行 `python3 scripts/obs_pack.py experiments/$EXP_ID` 生成观察包；
2. 运行 `python3 scripts/exp_index.py` 刷新关系表；3. 把控制权交给 `analyze-results` skill 做分析；
3. 按 `templates/experiment_log.md` 写一条实验记录到 notes/（若用户开启笔记功能）。

## 失败处理约定

- 栈启动超时（>120s 未 READY）：收集 launch.log 最后 50 行，调用 `analyze-results` 的故障速查表给出最可能原因，**不要盲目重试超过 1 次**；
- 任务中途坠机/failsafe：保留全部现场（bag 照常落盘），标记 `outcome=crash` 直接进分析——失败数据同样有价值；
- 任何一步非零退出码：停止后续步骤，如实报告。
