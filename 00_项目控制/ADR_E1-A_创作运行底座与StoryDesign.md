# ADR E1-A｜创作运行底座正式化与 StoryDesign 最小骨架

- 状态：已实现；E1-B / E1-C / E1-D 真实实验已完成，使用策略已冻结为 `BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`（见本文末节）。
- 范围：Phase E 的 E1-A；不实现 Writer、正文主链、Review、UI、数据库、全局 Router 或固定多 Agent 平台。
- 实现位置：`05_Skills与自动化/01_Skills/StoryDesign/`。

## 决定

以小型、文件型且 provider-agnostic 的 Python runtime 正式承载 G4 已验证的五类工件：Author Intent、Story State / Canon、Creation Brief、Context Package、Decision Record / State Diff。JSON 是 E1-A 的最小运行载体，不声明为最终 Canon Schema；历史 G4 YAML/Markdown 仍是已验证原型证据，而非需迁移的数据源。

StoryDesign 的 capability id 为 `story_design.v0`。它接收作者自然语言种子，接受模型/Skill 提供的语义理解作为显式输入，并形成 Brief、按需检索、少量 Context、noncanonical candidate 与 trace。其本地代码不判断人物、俗套、结局或读者欲望；这些判断属于模型与 StoryDesign Skill。代码只处理文件、ID、revision、authority、retrieval、provenance、stale 和 writeback guardrail。

## 复用的 G4 能力

- Author Intent 是方向权威；Story State / Canon 只接受 `accepted_text`、`author_decision` 或 `manual_import` authority。
- Brief 记录作者自然输入、source revisions 和 AI assumptions；assumption 不成为作者事实。
- Context 是可重建派生物，revision 不匹配即 stale；BKP 与 State 分区，BKP 不可成为 Canon authority。
- candidate 是 `proposal_noncanonical`；未确认候选不能建立 Decision、Diff 或 planning。
- confirmed creative change 只能由 Decision 产生并在 E1-A 写入 `approved_plan`；planning 条目强制 `occurred=false`，不等于 Canon。
- stale `base_state_rev`、无作者确认的 creative change、以及任何 `ambiguous_inference` 都被拒绝应用。

## 最小协议，而非最终 Schema

当前只稳定工件语义和机械边界。字段、文件拆分、模型提供方、Context 压缩策略、Canon 细粒度、任务路由和最终存储均保留演进空间。StoryDesign 唯一允许的写回目标是 `approved_plan`，因此它不能偷渡新人物事实、世界规则或已发生事件。

## BKP、proposal、planning 与 Canon

```text
BKP card ──检索/引用──> Context Package ──模型综合──> proposal_noncanonical
                                                     │
作者明确 Decision ──────────────────────────────────┘
                                                     ↓
                                           approved_plan (future, reversible)

accepted_text / author_decision / manual_import ───> Canon / Story State
```

单书 BKP 保留 source、knowledge/card id、scope、boundary、confidence 和 evidence。KnowledgeRetrieve 只召回候选；模型/Skill 必须显式选择 card id，runtime 只核验 id、provenance 和数量上限。`INSUFFICIENT_BKP` 或无语义选择都会记录 gap 并让模型使用一般创作能力继续，不会按排名硬凑卡片，也不会把全库注入 Context。

## 为什么没有固定多 Agent 流水线或全局 Router

StoryDesign 默认由一个强模型承担创作判断；人物、结构、读者体验等仅是按问题添加的 stance。固定流水线会把简单种子变成不必要的成本，也会假装多个结论独立。全局 Router 尚无真实跨能力调用问题需要它；本次仅公开 `story_design.v0` capability contract，未来 Router 可调用而不预置几十条规则。

## 上游 provenance（只借机制，未复制代码或提示文本）

| Repo | Pinned commit | License | 处理 | 实际借鉴 |
|---|---|---|---|---|
| `haowjy/creative-writing-skills` | `fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3` | Apache-2.0 | concept-only | Muse 式按需 stance、意图保留、探索先于确认。 |
| `Narcooo/inkos` | `8dee4cb2367ec40d986e9a69e4c3ec05e78e79a3` | AGPL-3.0 | concept-only | natural-language action surface、非正史 future branch 与 stale separation。 |
| `ExplosiveCoderflome/AI-Novel-Writing-Assistant` | `3763cd11af4af379e935a655652e76fe98f7f6af` | AGPL-3.0-only | concept-only | 可恢复 stage artifact、plan → execute → state feedback 的工程边界。 |
| `worldwonderer/oh-story-claudecode` | `0a34c6998263026ec6160320a89692cdaa53fe69` | MIT | concept-only | 中文长篇的 reader promise、钩子/期待/兑现作为可按需调用的专业视角。 |
| `anotherpanacea-eng/apodictic` | `3fb7abcdde23915f302e020a29920069a3885fd5` | CC BY-NC-SA-4.0 | concept-only | reader contract 与诊断不替作者作最终决定的边界。 |

因为本次没有复制或改编上游代码/文本，未引入 NOTICE 或第三方代码文件；上表仍保留可审计 provenance。尤其 AGPL 和 CC BY-NC-SA 上游不被引入本仓库实现。

## 真实 A/B 的下一步

选择两个明确不同的作者自然语言种子（一个信息充分、一个故意模糊），让同一模型产生 Brief/Context/candidate。作者只评价候选是否有助于继续设计，而不评价模板完整度。比较：assumption 是否可见、BKP 是否真的相关、模型能否保留未知项、作者 choose/modify 后 planning 是否准确且 Canon 未变化。任何真实缺口再窄改 E1-A；不自动进入 StoryPlan 或 Writer。

## E1-B / E1-C / E1-D 验证结果与冻结策略（2026-08-15）

三轮真实实验均已执行完毕，正式结论为 **`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`**；完整证据入口为 `06_工作区/E1_StoryDesign冻结结论_2026-08-15.md`。

- **E1-B（知识前置 A/B）**：前置较多知识会提高结构纪律，但可能损失人物自然度和生活质感；三组 B 输出趋同于固定策划语法，且真正专门的问题均应记为 `NO_USEFUL_BKP`。
- **E1-C（稀疏后置对照）**：“自由初稿 → 窄诊断 → 后置修订”优于知识前置策略，但尚不能把改善全部归因于 BKP；检索前的自由初稿已拥有绝大多数人物生命感与生活细节。
- **E1-D（独立边际价值消融）**：严格消融中 K016 对特定 W1 提供小幅、独立、可追溯增益；W2 保持 `NO_USEFUL_BKP`。

冻结边界：BKP 并非每次必要；0 张是正常路径；BKP 独立增益目前只得到窄证据支持；不得外推为“知识库越多越好”。

冻结的 StoryDesign 使用策略：强模型优先自由完成第一轮原创设计；不默认在第一轮设计前注入 BKP；第一轮之后先诊断真实薄弱点，只有存在明确知识缺口时才调用 KnowledgeRetrieve；BKP 默认允许 0 张，常规目标 0–1 张，只有不同卡分别解决不同明确缺口时才允许更多；KnowledgeRetrieve 返回 OK ≠ 必须使用知识卡，相关但没有独立增益的卡必须允许拒绝；BKP 主要用于 challenge、counterexample、gap filling、targeted deepening、boundary checking，不负责搭建第一版故事骨架；不默认生成分卷、多路线、风险清单、分层揭示、多时钟等固定策划形状；专业 stance / Agent 只在具体缺陷触发时使用；`NO_USEFUL_BKP` / `INSUFFICIENT_BKP` 是正常结果；作者可见结果优先保留人物、场景、关系和具体生活质感，trace/provenance 完整保存但不强迫作者阅读。

代码影响：无。E1-A runtime 的 0 BKP / gap 记录 / `proposal_noncanonical` / Canon 隔离路径已支持上述策略，本冻结只同步 Skill 使用策略与文档，不新增流程硬编码，也不新增上游（上游 provenance 保持 E1-A 已记录的五项 pinned commit）。
