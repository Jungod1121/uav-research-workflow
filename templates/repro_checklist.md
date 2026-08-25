# Reproducibility Checklist — {论文名/实验系列}
> 投稿前逐项打勾；很多顶会现在硬性要求。

- [ ] 配置全量快照（Hydra config 或 key=value 清单，含随机种子 seed=N）
- [ ] 代码 commit hash 固定（含子模块）；fork 归档防上游移动
- [ ] Docker image tag / 栈版本清单（PX4 v1.16, gz-harmonic, ros-humble, …）
- [ ] 数据集版本与下载校验（md5/链接）
- [ ] rosbag 原始数据归档位置（备份仓库 snapshot id）
- [ ] 图表全部由脚本生成（scripts → figures/），无手工截图
- [ ] 每张图能从 bag/wandb run id 一键重画
- [ ] 训练类实验: wandb run 链接 + checkpoint 存放位置
- [ ] 多次运行方差报告（≥3 seeds）
- [ ] 硬件规格说明（CPU/GPU 型号，供算力对比）
