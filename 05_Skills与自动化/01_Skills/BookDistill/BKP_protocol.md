# BKP v0.2 知识卡协议

## 1. 定位与边界

BKP（Book Knowledge Package）是参考作品完成蒸馏后的长期知识资产。它服务未来的 StoryDesign、StoryPlan、Writer 与 Review 调用；不代替原著，不保存全部工作过程，也不构成原创作品 Canon。

正常创作阶段检索 canonical knowledge cards，不重新搜索 Raw Discovery。单书知识最高默认仍为 Work-specific Pattern；不得由单书提升为 Cross-book Pattern 或 Production Rule。

## 2. 权威层与投影层

`knowledge/cards.md` 是 v0.2 的唯一日常知识权威层。每张卡必须可追溯至原著章节行号。

`author_view.md` 是从 cards 派生的八区作者可读投影：总览、剧情结构、时间线、人物系统、世界观、主题、文风与技法、商业/读者价值。它帮助作者快速理解一本书，但不是第二套知识源，不能单独增加、修改或证明知识。

Raw Discovery、Observer staging、Prompt、日志和中间草稿只保留在审计/工作区；它们不是日常检索层。

## 3. 每张知识卡

卡片以 `## KNNN｜标题` 起始，必须包含：

- `knowledge_level`：Observation、Inference、Work-specific Pattern 或 Deep Dive Knowledge；
- `dimension`、`use_stages`、`problem_types`、`scale`；
- `statement`：作品中实际成立的可调用结论；
- `function`、`conditions`、`mechanism`、`effect`：把关键信息转为“在何种条件下，如何扩写成可执行场景/结构”的调用支架；
- `scope`、`boundary`、`confidence`、`evidence`。

`evidence` 必须为 `chapters/NNNN.md#Lx`（可带行号范围）并能回到冻结 SourcePrepare 快照。`tags` 可选，仅用于辅助检索。卡片应陈述作品内方法与边界，而不是把它伪装为通用处方。

## 4. 兼容性与冻结边界

`KnowledgeRetrieve` 优先读取 `knowledge/cards.md`；没有 cards 的 v0.1 split files 继续按原适配器加载。因此《一九八四》《三体》等旧 BKP 不要求迁移。

当前冻结的是：卡片职责、必填调用字段、author_view 的非权威身份、证据回溯和单书认识论边界。暂不冻结 JSON schema、文件拆分、卡片数量、向量/RAG/KG 实现或固定 Deep Dive 次数。

## 5. 全书综合验收门（协议 0.3，新增不追溯）

新蒸馏的 BKP 在声明可检索之前，必须完成一次显式的全书综合审计，证明重要的全书级发现确实到达 canonical 可检索卡；这是完成门，不是第二套知识层。

- 审计对象：全部章节 discovery 证据 + `model.md` + `mechanisms.md` + `book_profile.md` + 实际执行过的 Deep Dive + `bkp/knowledge/cards.md`。
- 审计问题：哪些作品级/弧级/跨尺度机制实质解释了这本书？对 story_design / longform_plan / chapter_plan / scene_write / review / revise 哪些调用有用？每条重要且有证据支持的发现是否成为 canonical 卡？若否，是否因过局部/过弱/冗余/未证实/不可复用而显式排除？
- 不设固定卡数/固定类型维度/文学评分；实际作品决定相关性。计数只作描述性统计。
- 审计结果写入资产根目录 `BKP_ACCEPTANCE_REPORT.md`，必须包含一个围栏 ```json `acceptance_data` 块，字段：
  `schema`（=gowrite_bkp_acceptance/v1）、`book_id`、`title`、`source_sha256`（来源指纹）、`protocol`、
  `status`（PASS|REVIEW）、`canonical_card_count`、`findings[]`（`finding` + `accepted` + `card_ids[]`；
  不入卡时 `accepted=false` 且必填 `exclusion_reason`）、`unresolved_gaps[]`（`description` + `blocking`）、
  `retrieval_ready`（布尔，必须与 status 一致）。
- `scripts/acceptance_gate.py` 做确定性机械校验：身份/指纹与 `bkp/identity.json` 一致；报告的卡 id 真实存在、
  无重复；卡数一致；PASS 不得与 blocking 缺口共存；evidence 满足 `chapters/NNNN.md#Lx` 溯源（可解析
  SourcePrepare 快照时，章节文件必须存在）。全部通过且 `--write-identity` 时才写入 `acceptance` 块。
- `KnowledgeRetrieve` 对 `acceptance.required=true` 的包只在 `acceptance.status == "PASS"` 时纳入检索；
  REVIEW/非法一律排除。旧版 v0.1/v0.2 BKP 没有 acceptance 块，保持原有可检索行为（向后兼容，不迁移）。
