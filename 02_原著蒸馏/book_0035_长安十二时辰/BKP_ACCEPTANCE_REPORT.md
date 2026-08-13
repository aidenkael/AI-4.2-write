# BKP 验收报告：《长安十二时辰》（book_0035）

## 结论

**BOOKDISTILL_STRUCTURE_FREEZE_RECOMMENDED**。

冻结的双 Observer Discovery 已由总编辑收敛为 48 张可调用、可回溯的 BKP v0.2 cards；这次结论只冻结结构职责和检索合同，不声称单书结论是普遍写作规则，也不进入 Writer/Review 平台实现。

## 输入与压缩

| 项目 | 结果 |
|---|---:|
| 冻结 Discovery | 707（Observation 566 / Inference 93 / Boundary 48） |
| SourcePrepare | book_0035，24 章，v0.2.1 PASS |
| 最终 knowledge cards | 48 |
| 压缩比例 | 707 → 48，14.73:1（cards 占 6.79%） |

Raw Discovery 继续只留在只读实验审计层；正式 BKP 只保留 source snapshot、作品地图、profile、cards 与非权威 author_view。

## 结构验收

- `knowledge/cards.md` 是唯一 canonical 日常检索层；每张卡有 level、适用阶段、问题类型、尺度、statement、function、conditions、mechanism、effect、scope、boundary、confidence 和章节行号 evidence。
- `author_view.md` 有八区投影，仅用于作者快速阅读，不产生独立权威。
- `KnowledgeRetrieve` 优先 cards，输出 card `source_anchor` 与场景扩写字段；无 cards 时继续加载旧 split files。
- 在隔离暂存中运行 `book_distill.py bkp` 复核通过：v0.2、48 cards、所有 evidence 行号与 SourcePrepare 24 章边界一致。

## 六个真实创作问题

| 问题 | 顶级命中 | 结果 |
|---|---|---|
| 三层时钟互相接力 | K001 | PASS |
| 假结局同时开出新债 | K002 | PASS |
| 配给制揭示 | K004 | PASS |
| 受限信息制造参与式推理 | K006 | PASS |
| 章末钩子落在行动或决定 | K007 | PASS |
| 从一条线索扩成完整场景 | K033 | PASS |

这些 query 已进入 `KnowledgeRetrieve/test_knowledge_retrieve.py` 回归测试；验证的是可检索性、来源锚点和调用结构，不把命中结果包装为唯一创作答案。

## 兼容与测试

- 《一九八四》《三体》：PASS，仍按 legacy v0.1 split files 读取，未重跑或迁移。
- BookDistill：`python -m unittest discover -s tests -p "test_*.py"` → 80 passed, 0 failed。
- KnowledgeRetrieve：`python -m unittest -v test_knowledge_retrieve.py` → 4 passed, 0 failed。

## 保留边界

- 不新增第三个 Observer；“关键信息 → 如何扩写成场景”由 cards 的 `function / conditions / mechanism / effect` 承担。
- 不重跑 24 章 Discovery，不重新做完整文学分析，不修改 SourcePrepare 或实验仓库。
- 后续仅在新书或真实 StoryDesign / StoryPlan / Writer / Review 调用出现可验证问题时，做最小改动。
