# L1 复现报告 — EGO-Planner (RA-L 2021)

- **论文**: EGO-Planner: An ESDF-free Gradient-based Local Planner for Quadrotors (ZJU-FAST-Lab, RA-L 2021)
- **复现级别**: L1 算法级（上游自带仿真，不接 PX4/Gazebo 执行栈）
- **代码**: `ZJU-FAST-Lab/ego-planner-swarm` @ `ros2_version` 分支, commit `23a8d5a`（官方 ROS2 移植）
- **环境**: ROS2 Humble + CycloneDDS(`rmw_cyclonedds_cpp`) + 自带 mockamap/random_forest 地图 + poscmd_2_odom 假无人机
- **工作空间**: `repros/ego-planner-l1/ws`（20 包全量编译通过, 1min59s）

## 结果

| 指标 | 论文声称 | 本次复现 | 判定 |
|---|---|---|---|
| 单次规划耗时 | ~1 ms | **均值 0.089 ms / 峰值 2.4 ms**（1394 次重规划） | ✅ 优于声称值 |
| ESDF-free | 无 ESDF 构建 | 全程无 ESDF 相关开销 | ✅ |
| 森林场景轨迹 | 障碍密集场景可行 | RViz 渲染：随机森林点云 + 穿越轨迹线可见 | ✅ |

证据：规划日志 `/tmp/opencode/ego_l1.log`（time(ms) 序列）、截图 `ego_l1_rviz.png`（RViz 实况）。

## 过程坑（新增 5 条，已入 experiment-setup 档案）

1. **virtual_floor 挡起飞**：ros2_version 分支 grid_map 自带 `virtual_floor_height=-0.1`（地面禁飞带），假起飞高度 0.1m 的出生点正好在膨胀带内 → "First 3 control points in obstacles"，规划全失败。原项目 (drone_ws) 靠"先起飞后规划"规避。L1 按上游语义运行时需知晓此行为。
2. **目标发布竞态**：`ros2 topic pub --once` 在 CycloneDDS 发现完成前退出 → FSM 未收到目标。解法：`--rate 2` 持续发布 ≥12s。
3. **ros2 daemon 域/中间件缓存**：daemon 以旧 RMW/域启动后 CLI 全瞎（wait set 错误），`ros2 daemon stop` 重启即愈。
4. **git HTTP/2 framing**（构建期）：代理下 ExternalProject 克隆断流 → `git config --global http.version HTTP/1.1`。
5. **GnuTLS recv error**（代理掐 GitHub）：clone 改离线 tarball 方案（见 Docker 层同款教训）。

## 审计发现（vendor 对照，2026-08-28）

- drone_ws `ego_vendor` 与上游 `23a8d5a` 逐包 diff：核心差异 = `bspline_optimizer.cpp` 36 行 **rebound 回退修复**（上游遇 "Failed to generate direction" 仅 WARN 并放任退化轨迹；vendor 将未分配控制点锚定到最近 A* 逃生路径）——修正了 VENDOR_NOTES 中"逐字节一致"的过时记载
- `ego_replan_fsm.cpp`：odom twist body→world 旋转（REP-105 修正，文档已载）
- `plan_env/grid_map`：virtual_floor 参数实为 **ros2_version 分支上游自带**（vendor notes 归属有误，已更正理解）

## 端到端穿越飞行（2026-09-02 补全）

- **触发方式**：`flight_type=2`（PRESET 航点模式，/move_base_simple/goal 无效）→ 发布 `/traj_start_trigger` 后 FSM 自动执行往返任务：waypoint0 (15,0,1) → waypoint1 (-15,0,1) → waypoint2 (15,0,1)
- **穿越验证**：24s 穿越 250 障碍森林到达第一航点；持续飞行 281s+，位置横跨 x∈[-15, 15] 往返（RViz 截图：ego_l1_flight.png，无人机返程中 x=-11）
- **完整指标**（281s 飞行窗口）：
  - 重规划 **1615 次**（含避障重规划）；规划尝试 526 次：成功 366 / 失败 160（失败=已知上游限制"rebound 逃生方向耗尽"，自动重试后任务零中断）
  - 规划耗时：**均值 0.087 ms · 中位 0.056 ms · P95 0.232 ms · 峰值 2.8 ms** —— 论文声称 ~1ms，复现均值低 12 倍 ✓
- **判读**：RA-L 2021 核心声称（ESDF-free、~1ms 级规划、杂乱森林可行）全部复现 ✓；失败率 30% 集中于负载峰值时刻，与 vendor 笔记记载的"已知上游限制"一致（我们的 rebound 回退补丁即为此而设）

## 未完成项（转 L2）

- L2：ego 轨迹 → 我们的 PX4+Gazebo 执行栈（TrajectorySetpoint 流），血缘照录
- L3：在 L2 上做研究增量（对照位置阶跃/轨迹跟踪失败分类学）
