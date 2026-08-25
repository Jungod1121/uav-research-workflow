# EXP {EXP_ID} — {一句话标题}

- **日期**: {YYYY-MM-DD}
- **目标假设**: {本次实验验证什么，可证伪表述}
- **配置**: {key=value 全量，或指向 config 快照路径}
- **代码版本**: {git commit hash} · **镜像/栈**: PX4 v1.16 / gz-harmonic / humble
- **随机种子**: {seed} （仿真确定性来源：world 文件 hash）

## 结果摘要
{2-3 句。主指标数值 vs 上一轮/预期}

## 结论代号
F1-F6（见 analyze-results 失败分类学）: {如 F2 主导}

## 证据索引
- bag: experiments/{EXP_ID}/bags/
- 观察包: experiments/{EXP_ID}/obs_pack.md
- 诊断报告: experiments/{EXP_ID}/diagnosis_report.md

## 下一步
{给 iterate-experiment 或人工的具体动作}
