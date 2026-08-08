# B09 Round 01 Status

- 状态：`READY_FOR_LOCAL_SAMPLE_FREEZE`
- 更新时间：2026-08-09
- 当前阶段：实验协议与工具已就绪，等待本地 Agent 访问 `01_原始素材`。

## 已完成

- [x] Benchmark 总设计
- [x] B09 第一轮执行协议
- [x] 3 样本 × 2 窗口冻结规则
- [x] D0 / A / B / C 四 Runner 协议
- [x] Evidence / Interpretation / Mechanism Card 统一合同
- [x] 样本 SHA256 / 章节边界冻结器
- [x] Runner 输出确定性检查器
- [x] 匿名化工具
- [x] Blind Judge 协议
- [x] 本地 Agent 完整执行任务
- [x] 本地 manifest / run 目录加入 `.gitignore`

## 下一动作

本地 Agent 读取：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/README_本地执行任务.md`

然后执行 Phase 1–2：

1. 从 `01_原始素材` 选择 `WN-A`、`WN-B`、`WL-A`；
2. 运行 `05_Skills与自动化/scripts/b09_freeze_samples.py`；
3. 生成三个本地 manifest；
4. 核验三个 source SHA256 和 OPENING/MIDDLE 窗口；
5. 不运行 Runner，先把样本选择和冻结结果汇报给 Controller 做一次 sanity check。

## 当前阻塞

ChatGPT 当前 GitHub 连接能读写仓库，但不能读取本机 Local Only 的 `01_原始素材` 正文，因此无法在此环境直接完成 source freeze。该阻塞是数据访问边界，不是 Benchmark 设计缺失。

## 完成 Phase 2 后的下一状态

`SAMPLES_FROZEN_READY_FOR_RUNNERS`
