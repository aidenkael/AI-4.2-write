# AI-write 长期开发手册

> 更新日期：2026-08-15  
> 当前主线：**Phase E｜写作主链**  
> G5｜正文诊断与修订最小闭环：**PAUSED**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是一键自动写整本书，也不是一个“蒸馏工具项目”。

长期目标：

`参考/研究 → 构思 → 规划 → 写 → 审阅 → 修改`

后台能力链最终服务于：参考作品知识、自己的小说事实与状态、规划、上下文编译、正文生成、审阅修订和状态回写。

作者负责方向、审美、重要创作选择和最终取舍；后台像长期稳定的编辑部与创作团队，负责记忆、检索、规划辅助、诊断和机械维护。作者不需要管理 Agent、Skill、Prompt、Schema 或数据库。

## 1.1 “自研”的定义

自研不是重新制造 GitHub 上已经存在的能力。

默认路线：

`大量借用 / 复制 / 改造成熟项目`
`→ 少量自研连接层、知识协议和作者控制边界`
`→ 组成适合长期真实写作的一套工作台`

自研的核心是掌握：**架构、知识协议、数据边界、集成方式和验收标准**。具体能力可以由成熟开源项目、ChatGPT、Agent 或人工完成。

判断任何新开发是否值得做，首先问：**它是否让未来真实写作更好或更省事？如果成熟上游已经解决，就优先吸收。**

## 1.2 项目开发优先级

1. **第一：最终工作台能力**（作者可感知的真实创作能力）；
2. **第二：降低开发者维护 / 操作 / 验证 / 决策压力**；
3. **第三：子系统工程完整性**。

不得把“降低开发压力”解释为降低作品质量要求。

---

# 2. 已完成地基：参考作品进入 BKP

当前参考作品职责链已经跑通：

`SourcePrepare`
`→ BookProfile Scout`
`→ 多个互补观察视角直接读原著`
`→ 按需 Developmental Deep Dive`
`→ BookDistill 总编辑式收敛`
`→ BKP`
`→ KnowledgeRetrieve`

已有实现：

- SourcePrepare v0.2.1：作品身份、来源/版本、完整性、章节和标准 Markdown 输入；
- BookDistill v0.3：Evidence / Observation / Inference / Boundary、BookProfile、Deep Dive、总编辑收敛、BKP Finalize；
- BKP v0.2：`knowledge/cards.md` 为 canonical 日常检索层，`author_view.md` 为非权威作者投影；
- KnowledgeRetrieve：优先读取 cards；没有 cards 时兼容旧 v0.1 split files；
- 《一九八四》《三体》旧 BKP 兼容通过；
- 《长安十二时辰》正式验收：707 条冻结 Discovery → 48 张可追溯 cards，6/6 个真实创作问题检索通过。

因此：**BOOKDISTILL_STRUCTURE_FREEZE_RECOMMENDED。**

BookDistill 从现在起进入结构冻结状态。不再主动横向研究“怎样拆得更细”；以后只有新作品或真实 StoryDesign / StoryPlan / Writer / Review 调用暴露可验证缺口时，才做最小窄改。

Raw Discovery 是研究/审计层；正式 BKP cards 是正常创作调用层。Writer 或未来 Context Compiler 不直接搜索几百条 Raw Discovery。

---

# 3. Phase E 业务主链

当前确认的业务顺序：

`StoryDesign → Canon / Story State → StoryPlan → Context Compiler`

后续再继续接：

`StoryWrite → StoryReview → StoryRevise → State Writeback`

这条业务顺序不因为开发实现顺序改变。

## 3.1 当前具体开发顺序

Canon / Story State 最小权威协议、StoryDesign 运行底座（E1-A～E1-M）与 StoryPlan 最小合同（E2-A）均已完成并合入 main；知识介入策略已冻结为稀疏后置问题驱动。

E2-B 真实长篇规划纵切已完成并正式关闭（`E2B_VERTICAL_SLICE_PASS` / `E2B_STORYPLAN_REAL_VERTICAL_SLICE_CLOSED`）：0 张 BKP 的自由规划形成了可用长篇发动机，local relationship scope 局部规划成立且未重算全书，simulated writeback 的 Canon 隔离为零污染。八项结论与保留缺口以 `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/final_report.md` 为准。

E2-C 局部重规划已完成并正式关闭（`E2C_PASS` / `E2C_STORYPLAN_LOCAL_REPLAN_CLOSED` / `STORYPLAN_PHASE_CLOSED`）：append-only local replan / supersede / active projection / stale recompile / modify / Canon isolation 均成立；最终门禁 StoryPlan 50 tests OK、StoryDesign 27 tests OK、E1 runtime 零修改。

**E3-A Context Compiler 最小技术地基已完成并正式关闭（`E3A_PASS` / `E3A_CONTEXT_COMPILER_FOUNDATION_CLOSED`），已合入 main**。**NEXT_MAINLINE = STORYWRITE_REAL_VERTICAL_SLICE**（能力优先真实写作纵切）。原 E3-B 独立 Context Benchmark 取消 / 不执行：原因不是 Context Compiler 失败，而是 E3-A 已经证明其最小技术边界，现在必须由真实下游 consumer 验证价值；Context Compiler 进入 `CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE`，只有 Writer / Review / State Writeback 等真实下游消费者暴露可重复、可验证 blocker 时才允许回来窄改。StoryPlan 当前停止扩展；future consumer 暴露真实缺口前不继续建设 replacement engine / dependency graph / final Plan Schema。

原因：StoryDesign 在业务上发生在前，但它产生的人物、世界、冲突、关系和方向等内容需要有稳定的落点。先把“自己的小说事实怎样保存、哪些是权威、怎样更新”定稳，再实现 StoryDesign，可避免后续反复改接口。

这不等于把产品流程改成 `Canon → StoryDesign`；产品/业务顺序仍是 `StoryDesign → Canon / Story State`。

近端顺序：

1. ~~研究并确定 Canon / Story State 最小协议~~（已合入 main）；
2. ~~开发 StoryDesign~~（已合入 main）；
3. ~~开发 StoryPlan 最小合同~~（E2-A 已合入 main）；
4. ~~执行 E2-B StoryPlan 真实长篇规划纵切~~（已合入 main，E2-B 关闭）；
5. ~~执行 E2-C 局部重规划验证~~（已合入 main，E2-C 关闭，STORYPLAN_PHASE_CLOSED）；
6. ~~开发 Context Compiler 最小地基~~（E3-A 已合入 main，E3A_PASS / E3A_CONTEXT_COMPILER_FOUNDATION_CLOSED）；
7. ~~执行 E3-B Context Compiler 独立真实纵切~~（取消 / 不执行：E3-A 已证明最小技术边界，价值验证改由真实下游消费者承担）；
8. 执行 STORYWRITE_REAL_VERTICAL_SLICE 能力优先真实写作纵切（NEXT_MAINLINE）：用现有 StoryDesign / Story State / StoryPlan / Context Compiler 基础设施直接服务一段真实小说正文写作，验证已有能力链是否真的能服务小说写作，并反向暴露真实缺口。

尚未确认的具体 Canon 字段、Story State Schema、StoryDesign 输出结构不得提前写死。

---

# 4. 参考知识与原创事实必须隔离

这是后续写作主链的硬边界：

- **BKP**：参考作品中提炼出的写作知识、模式、观察和边界；
- **Canon / Story State**：我们自己正在创作的小说中已经确定或已经发生的事实与当前状态。

自己的小说事实和作者明确要求始终高于参考作品建议。参考书只能提供方法和启发，不能污染或覆盖原创作品 Canon。

结构化 Canon / Story State 属于权威数据；未来的向量索引、图索引等如果使用，只能是可重建的派生层，不能反过来成为事实源。

---

# 5. Phase E 的研发方式

继续执行 Borrow-first，但研究改为**按当前能力阶段定向进行**，不再做泛化的 GitHub 横向扫库。

开发某一阶段时，再研究与该阶段直接相关的成熟能力，例如：

- StoryDesign / Story Bible / Character / World；
- Canon / Memory / Story State；
- StoryPlan / 长篇规划；
- Context / Memory / Retrieval；
- Writer；
- Reader / Critic / Review；
- Revision / Continuity。

原则是按能力吸收，不按项目整套复制。案例只负责暴露真实问题，不负责决定永久架构。

---

# 6. 长期核心原则

## 6.1 Borrow-first

`真实问题 → 查成熟上游 → 能借就借 → 最小适配 → 真实运行`

不为了证明“自研”而重复实现成熟能力。

## 6.2 真实任务优先

能通过真实创作任务快速判断的问题，不升级成研究型 Benchmark；能在真实使用中暴露的问题，不提前过度设计。

## 6.3 CAPABILITY_FIRST_CONSUMER_DRIVEN（能力优先、消费者驱动）

- 最终作者可感知工作台能力优先于单个子系统完善度；
- 子系统达到最小合同并经过真实验证后默认冻结；
- 后续缺口由真实下游消费者暴露；
- 不为假设性未来需求提前 harden；
- 同等能力路线中，优先开发者维护压力更低的方案。

开发决策规则：只有同时满足（1）真实正文 / 真实使用暴露问题；（2）问题重复或足够严重；（3）直接模型 / 现有能力不能低成本解决；（4）新代码能明显降低长期作者 / 开发者负担，才允许建议开发新 runtime；否则 DO_NOT_BUILD。

## 6.4 案例只暴露问题，不决定架构

单本书、单个场景或一次模型表现不能直接升级成永久 Schema / Skill。

## 6.5 参考知识与原创事实分层

BKP 与 Canon / Story State 永远分开；自己的小说事实与作者要求优先。

## 6.6 作者控制 ≠ 作者审批

重要创作方向由作者控制；机械工作后台自动完成。只有真正存在创作歧义、冲突或高风险不可逆操作时才需要作者确认。

## 6.7 执行者适配优先

默认不固定必须由 ChatGPT、Agent 或用户本人完成任务。用户未指定时，根据成功率、操作简单度和合理成本选择执行者。

- **ChatGPT 更适合**：架构判断、方案设计、能力比较、协议 / Schema、GitHub 小型安全修改、结果审查、跨来源综合、知识压缩、BKP Chief Editor；
- **Agent 更适合**：本地多文件开发、长时间逐章/逐文件任务、pytest / build / CLI / 日志、本地数据库和文件系统、批处理、checkpoint / resume、执行—观察—修复循环；
- **混合任务**：只有当分工带来明确收益时才拆。不能为了“多模型协作”增加额外复杂度。

执行优先级：**操作简单与成功率 > 理论上的模型最优 > 过度细分工。**

## 6.8 基础模型创作能力优先，外部知识按需稀疏介入

AI-write 应优先发挥基础模型自身的综合创作能力。外部知识、BKP 和专业能力默认按需、稀疏、问题驱动地介入；只有真实创作问题暴露出明确知识缺口，且检索结果能提供额外价值时才调用。知识用于挑战、补洞、深化和边界提醒，而不是默认替模型搭建创作骨架。0 个知识命中/采用是合法结果。

## 6.9 新增能力必须证明边际价值

新增复杂能力必须证明边际价值；不能因为系统具备某项能力，就默认让所有任务经过它。

## 6.10 自由规划优先与 BKP 后置策略得到真实纵切支持

E2-B 真实长篇规划纵切验证：强模型自由规划优先原则继续成立——第一轮 0 张 BKP 即可形成可用长篇发动机；BKP 后置策略得到支持——Retrieval status=OK 时仍允许因为无独立增益而采用 0 张。

准确表述：本次 StoryPlan 案例没有召回真正有独立增益的 BKP，因此 `BKP_INDEPENDENT_VALUE = NO_USEFUL_BKP_AVAILABLE`；这不等同于“BKP 已证明没有价值”。

future planning 与 Canon 的隔离也真实通过：simulated writeback 的 `CANON_POLLUTION = ZERO`。

## 6.11 E2-B 保留的真实缺口

- `FREE_PLAN_QUALITY = PASS_WITH_RESERVATIONS`：P0 有轻度“策划委员会感”；初版父亲旧债存在“可拆除”问题；local relationship scope 说明该问题可通过更聚焦任务改善，但不能据此声称所有长篇规划质量问题已经解决。
- Retrieval 观察：当前检索对“责任 / 选择 / 后果”语义召回正常，但对“未解过去如何持续通过现在改变人物关系判断”的细粒度机制匹配不足。这是观察，不是现在重开 KnowledgeRetrieve / BookDistill 的理由。

## 6.12 StoryPlan 长期冻结原则

StoryPlan 已完成 E2-A（最小技术合同 / stable id / stale / Decision binding）、E2-B（真实长篇 planning vertical slice）与 E2-C（append-only local replan / supersede / active projection / stale recompile / modify / Canon isolation），阶段正式关闭（`STORYPLAN_PHASE_CLOSED`）。长期冻结以下原则：

1. 不使用固定 book/volume/arc/chapter/scene 层级作为 StoryPlan 基础架构；
2. `approved_plan` 保留 append-only history；
3. 当前有效 planning 是 derived view，不修改历史；
4. 局部重规划通过显式 supersedes 表达；
5. supersede 必须绑定当前 Brief 明确引用的 active planning source；
6. sibling / ancestor 默认不因局部重规划失效；
7. `built_from` 暂不承担 dependency graph / recursive stale propagation；
8. planning 永远不等于 Canon；
9. stale Brief 必须重新编译；
10. TEST_ONLY simulation authority 永远不等于作者真实确认；
11. StoryPlan 当前停止扩展；future consumer 暴露真实缺口前不继续建设 replacement engine / dependency graph / final Plan Schema。

`FREE_PLAN_QUALITY = PASS_WITH_RESERVATIONS` 仍保留 E2-B 的真实 reservation（见 6.11），不得改写为“长篇规划质量已经完全解决”。

## 6.13 Context Compiler 长期冻结原则

E3-A Context Compiler 最小技术地基已完成并正式关闭（`E3A_PASS` / `E3A_CONTEXT_COMPILER_FOUNDATION_CLOSED`）。长期冻结以下原则：

1. Context Compiler 不默认注入整个 Story State；
2. 模型/Skill 做 semantic relevance 判断；runtime 只验证引用真实性、当前性、authority、active/stale；
3. State selection 必须 explicit；空 selection 不得 fallback 全量 State；
4. `selected_story_state` 与 `selected_bkp_hits` 永远分区；
5. `approved_plan` 只能使用当前 active planning（superseded 历史保留在 append-only history 但不进 Context）；
6. planning source authenticity 延续 StoryPlan 边界：production 仅 `author_decision:` / `manual_import:`；simulation（`simulation_author_decision:`）仅 TEST_ONLY gate 可用；
7. Context Package 是可重建派生层，不是 Canon authority，永不写回 Story State；
8. Context stale 依赖 `brief_id` / `brief_rev` / `intent_rev` / `state_rev`；
9. 当前不做：最终 Context Schema、token budget optimizer、embeddings、vector DB、graph DB、Router、Writer prompt packing；
10. E3-A 只证明“可以安全地选少量上下文”，尚未证明“小上下文一定比全量上下文创作效果更好”；该问题不再通过独立 Benchmark 验证，而是并入真实下游创作消费者（STORYWRITE_REAL_VERTICAL_SLICE 起）的真实使用中反向验证。

Context Compiler 自 2026-08-15 起进入 `CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE`：独立的 E3-B Context Benchmark 取消 / 不执行；原因不是 Context Compiler 失败，而是其最小技术边界已由 E3-A 证明，继续价值必须由真实下游消费者（Writer / Review / State Writeback）暴露的可重复、可验证 blocker 驱动，才允许回来窄改。

---

# 7. 当前不做什么

当前不重新打开 BookDistill 横向研究，不继续 G5 沙盒正文，不要求作者评价测试文章。

Canon / Story State、StoryDesign 与 StoryPlan 最小合同已经定稳；当前仍不优先开发：

- 完整 Writer 平台；
- 大型 RAG / Knowledge Graph；
- 大型多 Agent 编排平台；
- UI；
- 为全部素材提前建设批量蒸馏基础设施；
- 为了“一键化”重构已经稳定的 SourcePrepare / BookDistill。

SourcePrepare 与 BookDistill 保持可分开执行。未来真正出现批量提纯、批量蒸馏的重复操作后，再补薄的批处理入口，不让产品体验反过来决定文学方法。

---

# 8. 当前阶段完成标准

当前阶段首先要证明：

> **原创小说的核心设计可以进入稳定、可维护、不会被参考知识污染的 Canon / Story State；随后 StoryPlan 和 Context Compiler 能消费这些权威状态，并按真实创作任务调用少量相关 BKP 知识。**

E2-B 已证明：StoryPlan 能从权威状态出发做真实长篇规划（0-BKP 可用长篇发动机），local scope 成立，未来规划不污染 Canon（CANON_POLLUTION=ZERO）。保留缺口：规划质量存在轻度“策划委员会感”与初版父亲旧债“可拆除”问题，不能据此声称所有长篇规划质量问题已经解决。

不是先做一个庞大的“全功能 AI 作家”。

---

# 9. Git 与文档纪律

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

本地 dirty / untracked / stash 先识别内容再处理，不自动 pop/drop/clean，不为了普通同步建立无意义长期分支。

长期文档只留稳定原则和当前路线；具体过程放工作区和 Git 历史。能修改已有文档解决的问题，不新增补丁式说明文件。

当前入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。

---

# 10. 一句话总纲

> **参考作品学习链已经完成结构冻结；StoryDesign 运行底座、StoryPlan 最小合同、真实长篇规划纵切（E2-B）与局部重规划（E2-C）均已通过并关闭（STORYPLAN_PHASE_CLOSED；append-only history、active projection、Canon 隔离零污染成立）；Context Compiler 最小技术地基已合入 main 并正式关闭（E3A_PASS / E3A_CONTEXT_COMPILER_FOUNDATION_CLOSED），并进入 CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE（E3-B 独立 Context Benchmark 取消）；知识介入策略冻结为稀疏后置问题驱动；开发优先级：最终工作台能力 > 降低开发者压力 > 子系统工程完整性（CAPABILITY_FIRST_CONSUMER_DRIVEN）；NEXT_MAINLINE = STORYWRITE_REAL_VERTICAL_SLICE（能力优先真实写作纵切）。**
