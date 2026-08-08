# B09 Round 01 Status

- 状态：`SAMPLES_FROZEN_READY_FOR_RUNNERS`
- 更新时间：2026-08-09
- 当前阶段：Phase 1–2 已完成，三个第一轮样本已冻结并通过 Controller sanity check，准备进入 Runner 对照实验。

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
- [x] Phase 1：检查本地来源并筛除明显污染样本
- [x] Phase 2：冻结 WN-A / WN-B / WL-A 三个样本
- [x] Controller sanity check：窗口、覆盖声明、非重叠与源文件保护通过
- [x] `06_工作区/SourcePrepare/` 加入 `.gitignore`，防止派生全文误上传

## 第一轮冻结样本

### WN-A：《庆余年》

- 类别：网络小说
- 边界模式：chapter
- 探测章节：750
- OPENING：span 1–6
- MIDDLE：span 373–378
- 结论：通过。开篇与中段相距足够远，适合检查开篇机制与中段漂移。

### WN-B：《道诡异仙》

- 类别：网络小说
- 边界模式：chapter
- 探测章节：1042
- OPENING：span 1–6
- MIDDLE：span 519–524
- 结论：通过。源文本较干净，替代存在占位/串书污染的候选样本。

### WL-A：《一九八四》

- 类别：世界文学
- 来源：本地 SourcePrepare 派生干净文本；原始来源仍只读保留
- 边界模式：segment fallback
- 可用 segment：19（每段目标约 10,000 字符）
- OPENING：segment 1–6
- MIDDLE：segment 7–12
- 结论：通过。虽然段号从 7 开始，但 6 段窗口的中心约落在全书 segment 9.5–10 附近，属于合理的中点窗口，不需要修改冻结器。必须保留 `coverage=sampled`，不得把两个窗口外推为全书规律。

## 样本筛除记录

- 《琅琊榜》：开头约 14 章存在“编辑正在处理中”等爬虫占位，不进入第一轮。
- 《孺子帝》：尾部混入其他小说片段，不进入第一轮。
- 《诡秘之主》：尾部混入其他小说片段，不进入第一轮。

这些污染本身说明未来正式蒸馏前需要独立的 Source Quality Gate；本轮先不扩展 B09 范围。

## 下一动作：Phase 3 Runner 对照实验

本地 Agent 先同步 `main` 最新提交，再严格读取：

- `05_Skills与自动化/B09_原著蒸馏Benchmark/README.md`
- `00_项目控制/B09_原著蒸馏Benchmark_执行协议_v0.1.md`

随后对 3 个样本 × 2 个窗口分别运行：

1. D0：Baseline
2. A：oh-story 方法
3. B：ani-book 方法
4. C：AI-write Candidate

总计 24 个 Runner 输出（3 作品 × 2 窗口 × 4 Runner）。

要求：

- 每个 Runner 只读取 manifest 指定窗口；
- 每次运行前重新核对 source SHA256；
- 四套 Runner 输入范围和模型条件保持一致；
- Runner 彼此看不到其他输出；
- 输出必须遵守 Evidence → Interpretation → Mechanism Card 合同；
- 不运行 Blind Judge，先完成 Runner + 确定性检查；
- 如果某个输出 deterministic check 失败，只修复该 Runner 输出，不改变其他组实验条件；
- Phase 3 完成后暂停，汇报每组 check 结果、失败类型、Token/上下文成本（可获得时）和异常，不提前宣布赢家。

## 当前阻塞

无设计阻塞。原著正文仍为 Local Only，因此 Phase 3 必须由有本地文件访问权限的 Agent 执行。

## Phase 3 完成后的下一状态

`RUNNERS_COMPLETE_READY_FOR_BLINDING`
