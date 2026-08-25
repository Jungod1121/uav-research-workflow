---
name: paper-annotation
description: 执行金标签论文标注任务：按 Atlas annotation_package 的固定 prompt 结构与输出格式，对一批论文做 taxonomy 多轴标注（LLM-as-judge）。触发词：标注论文、金标标注、annotation、继续标 part。
---

# Paper Annotation — 金标标注固化流程

背景：Atlas 的校准依赖外部 LLM-as-judge 金标签（见 Atlas `docs/validation.md`）。本 skill 把已验证有效的标注任务结构固化，保证每批标注口径一致。物料位置：`~/work/uav-research-atlas/data/annotation_package/`（part_01..05.md 为批次文件）。

## 输入

- 一个批次文件（如 `part_03.md`），内含 N 篇论文的标题+摘要；
- taxonomy 参考：`data/seed_taxonomy.json` 四轴节点定义（method/environment/sensor/application）。

## 标注规则（与 Atlas 分类流水线同一严格口径，逐条遵守）

1. **只标注论文实际研究/使用/实验验证的内容**；引言动机里提及的场景、related work 里引用的方法都不算证据;
2. 综述/仿真平台/数据集类论文从轻标注（只标明确自述的轴）;
3. 每轴**最多 2 个标签**，宁缺毋滥——不确定就不标;
4. 每个标签附 0–1 置信度 + 一句证据引用（摘要原文短语）;
5. 物理矛盾组合直接不标（如 GNSS × GPS-denied）。

## 输出格式（固定 JSON，勿改字段名）

对每篇论文输出：

```json
{
  "arxiv_id": "2401.12345",
  "tags": {
    "method": [{"node": "SLAM", "conf": 0.9, "evidence": "we propose a LiDAR-inertial odometry"}],
    "environment": [],
    "sensor": [{"node": "LiDAR", "conf": 0.85, "evidence": "Livox Mid-360"}],
    "application": []
  },
  "notes": ""
}
```

全部结果写入批次同名结果文件 `annotation_package/results/part_XX.json`。

## 流程

1. 读批次文件 → 逐篇按上述规则打标 → 写结果文件；
2. 自检一遍：对照 seed_taxonomy 节点名拼写（大小写、连字符）完全一致；发现节点缺失时不要发明新节点，记入 notes;
3. 完成后提示用户可执行导入与报告：
   ```bash
   cd ~/work/uav-research-atlas/backend && .venv/bin/python scripts/import_annotations.py --dir ../data/annotation_package/results
   .venv/bin/python scripts/annotation_report.py
   ```

## 一致性要求

跨批次一致性优先于单篇最优：拿不准的边界 case 记录到 notes 而不是强行归类；同一模式（如"仿真验证的环境轴算不算标注"）在整批内保持同一处理。
