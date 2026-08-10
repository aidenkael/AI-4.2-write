# 蒸馏报告：一九八四（book_0038）

> 本报告为 BookDistill v0.1 pilot 的最终状态报告。
> 作者综合层产物：`model.md`（第一阅读入口）、`mechanisms.md`（可迁移机制）、
> `evidence.md`（精选证据索引）。逐章底稿保留于 `evidence/ch_NNNN.md`。

## 一、来源身份（provenance）

- **book_id**：`book_0038`
- **书名**：一九八四
- **BookDistill 版本**：`0.1.1`
- **SourcePrepare 版本**：`0.2.1`
- **SourcePrepare 状态**：`PASS`
- **选定来源 SHA256（source_sha256）**：`a426098082241b8260ee67112dd656e7677f3d90dab323083f2d0338322a5627`
- **章节数（chapter_count）**：24
- **BookDistill 输入内容 fingerprint（chapter_content_fingerprint）**：
  `8d7e59437051e3381e462ded6025096078b911c81c078b8560f0fa990c13d62a`
  （按稳定章节顺序对 `chapters/NNNN.md` 文件名 + 文件字节聚合 SHA256；0000 前置不计入）
- **输入一致性**：assemble 校验通过（errors=0），现行 manifest 与输入 snapshot 精确匹配；
  输入章节内容变化后 assemble 将拒绝复用旧产物。

> 来源身份说明：原始素材真实文件路径属 Local Only（`metadata.json` 不上传）；
> 以上字段已固化进 `distill_manifest.json` 与本报告，保证 tracked 产物可追溯且不含原始路径。

## 二、覆盖情况

- **逐章底稿覆盖**：24/24 章，无缺章（`evidence/ch_0001.md ~ ch_0024.md`）。
  第一部（0001–0008）：世界规则展示与日记开端；
  第二部（0009–0018）：爱情、兄弟会与被捕；
  第三部（0019–0024）：友爱部改造与结局。
- **原始 chapter-evidence 条目**：348 条（FACT 169 / INFERENCE 46 / MECHANISM 85 / BOUNDARY 48）。
- **机制收敛**：85 条原始 MECHANISM → 跨章合并/降级后保留 **15 条**正式机制（见 `mechanisms.md`）。
- **精选证据**：`evidence.md` 精选 **70 条**（FACT 55 / INFERENCE 8 / BOUNDARY 7），
  支撑全部 15 条机制与 `model.md` 各项结论；不替代 348 条逐章底稿。
- **校验状态**：assemble 通过，errors=0，warnings=0；全部证据引用行号均落在
  对应章节实际行数范围内。

## 三、方法

- **阅读范围**：完整阅读 SourcePrepare PASS 产物
  `06_工作区/SourcePrepare/book_0038_一九八四/chapters/0001.md ~ 0024.md` 全部 24 章；
  未读取 `01_原始素材` 中的 epub 原文，不重跑逐章分析。
- **分析方式**：evidence-first 逐章蒸馏（348 条底稿）→ 跨章验证 → 去重合并 →
  反例检查 → 重要性筛选 → 作者化表达，产出 `model.md` / `mechanisms.md` / `evidence.md`。
- **脚本纪律**：脚本只做机械校验（分类合法、引用可追溯、行号越界、source snapshot），
  不做语言分析；分析内容由 Agent 依据证据底稿填写。
- **译本说明**：正文为上海译文版中译本（source SHA256 见上）。

## 四、边界与不确定性（limitations）

1. **译本影响**：全部条目基于单一中译本；新话术语、童谣互文与"英语缺韵"等
   文化互文受译者选择影响，跨译本比对未做。
2. **人物观点 vs 作者立场**：如"神志清醒是统计数字"（0022）与"神志清醒不是统计数字
   所能表达"（0017）、结尾"他热爱老大哥"（0024）均为人物内心表述，
   不得单独援引为作者立场或作品主张。
3. **虚构文件边界**：书中之书（0017/0021）与附录《新话的原则》（0024）为小说内虚构文本，
   其论证/术语不可作为真实历史、语言学或政治学结论。
4. **单方陈述**：奥勃良关于兄弟会、书中之书、恋人行为的陈述为审讯场景单方证词，
   与后文对照存在张力，引用时须标注其不可靠性。
5. **不随意外推**：机制为写作技法层面归纳，可迁移性须在目标作品上重新验证；
   不构成创作效果保证；不把"机制存在"写成"已验证能力"。
6. **101 号房**：内容因人而异，揭示后亦须区分"预期恐惧"与"实际伤害"。
7. **门禁边界**：本 pilot 为 G1 最小验证产物，状态待作者审阅；不宣称
   "G1 完成""BookDistill 已验证"或"可进入 G2"。

## 五、产物清单

| 文件 | 角色 |
|---|---|
| `model.md` | 作者第一阅读入口：整体写作模型（14 节） |
| `mechanisms.md` | 可迁移机制集：85 条收敛为 15 条，含反证/失败模式/最小迁移测试 |
| `evidence.md` | 精选证据索引：70 条，支撑 model/mechanisms |
| `evidence/ch_NNNN.md` | 逐章证据底稿（348 条，audit appendix，保留不删） |
| `distill_manifest.json` | assemble 校验清单 + source snapshot（book_id/SP version/source_sha256/chapter_count/fingerprint） |
| `chapters_index.md` | 章节索引与引用规范 |

## 六、当前状态

**`G1_PILOT_AWAITING_AUTHOR_REVIEW`**

- 状态含义：pilot 综合完成，等待作者审阅判断蒸馏产物是否有用；
- 未声明事项：G1 未完成、BookDistill 未验证、不得进入 G2。
