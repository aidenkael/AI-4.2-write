# B02-G Round 2A｜Blind Map Pre-run Seal v0.1

> 日期：2026-08-10
> 状态：**mapping 已在任何正式 output 生成之前封存。** 内容 Local Only，作者全部评审封存之前不得揭盲。

## 一、封存对象

- 文件：`blind_map_presealed_r2a.json`（Local Only）
- 位置：`06_工作区/01_待处理/B02_情绪传递Benchmark/`
- 生成时机：**在任何正式 output 生成之前**（12 个正式 run 启动前完成封存）

## 二、SHA256

`329a4b97f222f527998031476741b8f48dddd9d17980e8613683b8711419d23f`

## 三、约束验证

新 mapping 满足全部平衡约束：

- G1–G4 每组均为 D0 / M1 / M2 各一次；
- 每个 condition 在 A/B/C 四组中的位置分布为 2/1/1；
- 同一 condition 未在相邻两组保持同一个字母；
- 与已作废的旧 mapping（`PRE_RUN_MAPPING_EXPOSURE`）四组均不同。

生成方式：从全部满足约束的候选 mapping 中由 `secrets.SystemRandom`（无 seed）随机选取，未进行人工挑选。

## 四、Local Only 边界

- mapping 内容仅存在于 `blind_map_presealed_r2a.json`；
- 不写入任何 tracked 文件、Git commit、STATUS 或作者可见文件；
- `blind_map_presealed_r2a.json` 与 `run_order_r2a.json` 已加入 `.gitignore` 保护。

## 五、揭盲条件

作者全部 4 组评审完成并封存（`author_blind_review_record_r2a.md`）之后，才允许：

- 揭盲；
- Controller 阅读正文；
- condition 级成本比较；
- 机制诊断；
- Round2A 结果分析。
