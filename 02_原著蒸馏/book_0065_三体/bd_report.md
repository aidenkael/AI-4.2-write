# 蒸馏报告：三体（book_0065）

> 本报告为 BookDistill v0.1.1 的 G2 第二份真实原著蒸馏最终状态报告。
> 作者综合层产物：`model.md`（第一阅读入口）、`mechanisms.md`（可迁移机制）、
> `evidence.md`（精选证据索引）。逐章底稿保留于 `evidence/ch_NNNN.md`。

## 一、来源身份（provenance）

- **book_id**：`book_0065`
- **书名**：三体（《三体》全集：地球往事 / 黑暗森林 / 死神永生）
- **BookDistill 版本**：`0.1.1`
- **SourcePrepare 版本**：`0.2.1`
- **SourcePrepare 状态**：`PASS`
- **选定来源 SHA256（source_sha256）**：`0fb3cde2dc4f8c9f4e5a2ba612f3d3d3eb049d67928cce4fcc8b2c94ea20c6a8`
- **章节数（chapter_count）**：42
- **BookDistill 输入内容 fingerprint（chapter_content_fingerprint）**：
  `76df501c055d5d211c15d6fe572bf21bc821b80e74a139a61eb915c9c36c8603`
  （按稳定章节顺序对 `chapters/NNNN.md` 文件名 + 文件字节聚合 SHA256；0000 前置不计入）
- **输入一致性**：assemble 校验通过（errors=0，warnings=0），现行 manifest 与输入 snapshot 精确匹配；
  输入章节内容变化后 assemble 将拒绝复用旧产物。

> 来源身份说明：原始素材真实文件路径属 Local Only（`metadata.json` 不上传）；
> 以上字段已固化进 `distill_manifest.json` 与本报告，保证 tracked 产物可追溯且不含原始路径。

## 二、覆盖情况

- **逐章底稿覆盖**：42/42 章，无缺章（`evidence/ch_0001.md ~ ch_0042.md`）。
- **输入结构**：0001–0035 为《三体》第一部（地球往事）35 章；0036 单章承载尾声·遗址、
  后记及整部《三体II·黑暗森林》（10115 行）；0037–0042 为《三体III·死神永生》六部。
- **原始 chapter-evidence 条目**：899 条（FACT 390 / INFERENCE 181 / MECHANISM 244 / BOUNDARY 84）。
- **机制收敛**：244 条原始 MECHANISM → 跨章合并/降级后保留 **17 条**正式机制（见 `mechanisms.md`）。
- **精选证据**：`evidence.md` 精选 **74 条**（FACT 61 / INFERENCE 5 / BOUNDARY 8），
  支撑全部 17 条机制与 `model.md` 各项结论；不替代 899 条逐章底稿。
- **校验状态**：assemble 通过，errors=0，warnings=0；全部证据引用行号均落在
  对应章节实际行数范围内，章节数精确匹配 42。

## 三、方法

- **阅读范围**：完整阅读 SourcePrepare PASS 产物
  `06_工作区/SourcePrepare/book_0065_三体/chapters/0001.md ~ 0042.md` 全部 42 章；
  未读取 `01_原始素材` 中的 epub 原文，不重跑逐章分析。
- **分析方式**：evidence-first 逐章蒸馏（899 条底稿）→ 跨章验证 → 去重合并 → 反例检查 →
  重要性筛选 → 作者化表达，产出 `model.md` / `mechanisms.md` / `evidence.md`。
- **脚本纪律**：脚本只做机械校验（分类合法、引用可追溯、行号越界、source snapshot、章节数匹配），
  不做语言分析；分析内容由 Agent 依据证据底稿填写。
- **版本说明**：正文为中文 epub 拆分文本（《三体》全集，42 章），非纸书页码；跨版本比对未做。

## 四、边界与不确定性（limitations）

1. **巨型章节样本不均**：0036 单章（10115 行，340571 字符）承载整部《三体II·黑暗森林》及尾声/后记，
   其证据密度与行号跨度远高于普通章节；跨段引用时须注意其大跨度性质，三册结构判断不得仅凭该章。
2. **递进式主角**：全书为汪淼→罗辑→程心多视角递进，机制归纳按"叙事功能"而非单一主角；
   人物观点的承接关系（如程心的两次选择）与作者立场之间必须保持距离。
3. **人物/叙述者观点边界**：威慑度（敌方评估）、"好战种族"（三体元首）、"傲慢"（白Ice）、
   "两次以爱的名义把世界推向深渊"（叙述者判断）均为书内观点，不得单独援引为作者立场。
4. **虚构文件边界**：三体游戏、解密档案、审讯笔录、童话、歌者视角、回归运动声明均为小说内虚构文本，
   其论证/术语不可作为真实科学、历史或政治学结论。
5. **游戏内历史人物**：周文王、孔子、秦始皇等为游戏内虚构角色，与真实历史无关，不可混用。
6. **版本影响**：全部条目基于单一中文拆分文本；术语（如"威慑度""二向箔"）与行文受排版/版本影响，
   跨版本比对未做。
7. **不随意外推**：机制为写作技法层面归纳，可迁移性须在目标作品上重新验证；
   不构成创作效果保证；不把"机制存在"写成"已验证能力"。
8. **门禁边界**：本产物为 G2 第二份真实原著蒸馏（book_0038 为 G2 第一份），G2 仍进行中、
   等待作者审阅；机制效果是否提升创作仍待真实创作验证，BookDistill 未达到生产级 / M5。

## 五、产物清单

| 文件 | 角色 |
|---|---|
| `model.md` | 作者第一阅读入口：整体写作模型（14 节） |
| `mechanisms.md` | 可迁移机制集：244 条收敛为 17 条，含反证/失败模式/最小迁移测试 |
| `evidence.md` | 精选证据索引：74 条，支撑 model/mechanisms |
| `evidence/ch_NNNN.md` | 逐章证据底稿（899 条，audit appendix，保留不删） |
| `distill_manifest.json` | assemble 校验清单 + source snapshot（book_id/SP version/source_sha256/chapter_count/fingerprint） |
| `chapters_index.md` | 章节索引与引用规范（含 42 章标题） |

## 六、当前状态

**`G2_IN_PROGRESS_BOOK0065_DISTILLED_AWAITING_AUTHOR_REVIEW`**

- 状态含义：book_0065《三体》蒸馏产物已完成并自检通过（assemble errors=0），
  等待作者实际审阅 model.md / mechanisms.md；G2 保持进行中，未进入 G3。
- 未声明事项：17 条机制未验证为能提升创作效果（延后到真实作品创作中验证）、
  BookDistill 未达到生产级 / M5、新机制未写入已验证生产规则。
