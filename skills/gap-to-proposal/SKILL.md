---
name: gap-to-proposal
description: 把 Atlas 中选中的 gap cell（如 VLA × GPS-denied）转成开题答卷：拉取格子论文分布、归纳 baseline/数据集/评测指标、生成开题骨架、文献清单可推入 Zotero。触发词：开题、写 proposal、这个空白怎么做、gap to proposal。
---

# Gap to Proposal — 从研究空白到开题答卷

输入：一个 gap cell 的两轴节点名（如 `method=VLA` × `environment=GPS-denied`）或用户口语描述。前置条件：Atlas 后端在运行（`http://localhost:8000`，未运行则提示用户 `cd backend && .venv/bin/uvicorn app.main:app --port 8000`）。

## 流程

### 1. 拉取证据（Atlas API，只读）

```bash
# 格子详情：样本论文 + 年份直方图 + 五类稀疏成因假设
curl -s localhost:8000/api/gap/{axisA_node_id}/{axisB_node_id}
# 节点论文清单（baseline 归纳的数据源）
curl -s "localhost:8000/api/papers?node_id={id}&sort=citations"
```

- 先 `GET /api/taxonomy` 拿节点 id 映射；
- 记录格子的 `sparsity/gap_score` 与解释层的成因类别——**若成因不是 true_gap/emerging_too_new，开题第一段必须直面该风险**；
- 论文数量随时间趋势从年份直方图读出：窗口正在关闭的格子要提示紧迫性。

### 2. 归纳「要跟谁比」（人工审核点）

从样本论文的标题/摘要中提取并列表：

| 维度 | 提取内容 | 产出 |
|---|---|---|
| Baseline | 该格子及相邻格子高频出现的方法/系统（如 ORB-SLAM3、FAST-LIO2、Ego-Planner…） | 候选 baseline 清单 + 各自开源地址 |
| 数据集 | 论文实际用的评测数据（EuRoC、Newer College、自采仿真…） | 推荐数据集 + 是否覆盖目标环境轴 |
| 指标 | ATE/RPE/成功率/最小间距/计算耗时… | 指标表（注明哪些是社区默认、哪些需自定义） |

**规则**：只归纳论文中"实际使用"的内容（与 Atlas 分类 prompt 同一严格口径）；每项标注来源论文名。此表必须交用户确认后才进入第 3 步。

### 3. 生成开题骨架（templates/proposal.md 结构）

写入 `~/work/uav-research-workflow/proposals/{YYYYMMDD}-{slug}/proposal.md`，核心章节：

1. 空白陈述（引用 gap_score 与成因假设，含可证伪表述）
2. 问题定义与范围（明确不做什么）
3. 相关工作分层（按 taxonomy 四轴组织，不用流水账）
4. 方法设想（占位，由用户填充——AI 不代替选题决策）
5. 实验计划（直接复用第 2 步的 baseline/数据集/指标表）
6. 风险与回退（成因假设为 feasibility_barrier 时必填）

### 4. 文献同步（Zotero，本机 localhost:23119）

- 前置：Zotero 桌面端开启（Better BibTeX 插件建议安装）；
- 将第 2 步确认后的论文清单导出为 BibTeX 文件 `refs.bib` 放入同目录；
- 同步方式按优先级：
  1. 若 Zotero 本地 API 可用（`curl -s localhost:23119/api/users/0/items` 探活）：生成 RIS 并提示用户拖入/导入；
  2. 否则仅落盘 `refs.bib`，并在 LaTeX 工程中直接 `\bibliography{refs.bib}`（Better BibTeX 用户也可改为引用其自动导出的库文件路径，避免双份维护）;
- 不做静默写入 Zotero——所有入库动作给用户可见的命令或文件。

## 输出物清单

```
proposals/{YYYYMMDD}-{slug}/
├── proposal.md        # 开题骨架（第4章留白待用户）
├── baselines.md       # 第2步确认后的对照表
└── refs.bib           # 文献库
```

## 红线

- 「稀疏 ≠ 机会」：全程沿用 Atlas 中性措辞，不使用"蓝海/风口"类表述；
- AI 不替用户决定做不做这个题——产出的是决策材料，不是决策。
