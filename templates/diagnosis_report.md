# Diagnosis — {EXP_ID}

## 一句话结论
{例：任务完成，但 WP3 转角超调 0.8m，属 F2 控制超调；置信度高（数据+截图一致）}

## 证据表
| # | 观察 | 类型 | 证据 | 置信度 |
|---|---|---|---|---|
| 1 | {轨迹末端偏移 0.4m} | 数据 | traj_plot.png + bag@t=42s | 高 |
| 2 | {WP3 处明显侧倾} | 视觉 | views/view_103022.png | 中 |

**数据/视觉矛盾记录**: {如有矛盾必须写明以哪个为准及理由}

## 失败分类
主导: F{X}-{名称}；次要: {…}

## 下一步建议（给 iterate-experiment 直接消费）
```yaml
# 每条建议 = 一轮迭代的配置覆盖
overrides_1: [mission.speed=1.0]
rationale_1: "{为什么这个改动可能改善}"
expected_metric: corner_overshoot_max ↓
```
