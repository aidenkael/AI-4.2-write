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

**NEXT_MAINLINE = E2-C_STORYPLAN_LOCAL_REPLAN_VALIDATION**（尚未启动）：只验证作者修改/否定已确认的局部 planning 时，能否只替换目标 planning、旧 planning 如何标记 superseded/stale、无关 sibling 与 ancestor 是否保持、已发生 Canon 是否保持、是否不因局部修改重算全书；不设计完整 replacement engine。

原因：StoryDesign 在业务上发生在前，但它产生的人物、世界、冲突、关系和方向等内容需要有稳定的落点。先把“自己的小说事实怎样保存、哪些是权威、怎样更新”定稳，再实现 StoryDesign，可避免后续反复改接口。

这不等于把产品流程改成 `Canon → StoryDesign`；产品/业务顺序仍是 `StoryDesign → Canon / Story State`。

近端顺序：

1. ~~研究并确定 Canon / Story State 最小协议~~（已合入 main）；
2. ~~开发 StoryDesign~~（已合入 main）；
3. ~~开发 StoryPlan 最小合同~~（E2-A 已合入 main）；
4. ~~执行 E2-B StoryPlan 真实长篇规划纵切~~（已合入 main，E2-B 关闭）；
5. 执行 E2-C 局部重规划验证：局部 planning 的替换 / supersede / stale / replacement 边界；
6. 开发 Context Compiler，把当前创作任务需要的自身小说状态与相关 BKP 知识编译成克制上下文。

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

## 6.3 案例只暴露问题，不决定架构

单本书、单个场景或一次模型表现不能直接升级成永久 Schema / Skill。

## 6.4 参考知识与原创事实分层

BKP 与 Canon / Story State 永远分开；自己的小说事实与作者要求优先。

## 6.5 作者控制 ≠ 作者审批

重要创作方向由作者控制；机械工作后台自动完成。只有真正存在创作歧义、冲突或高风险不可逆操作时才需要作者确认。

## 6.6 执行者适配优先

默认不固定必须由 ChatGPT、Agent 或用户本人完成任务。用户未指定时，根据成功率、操作简单度和合理成本选择执行者。

- **ChatGPT 更适合**：架构判断、方案设计、能力比较、协议 / Schema、GitHub 小型安全修改、结果审查、跨来源综合、知识压缩、BKP Chief Editor；
- **Agent 更适合**：本地多文件开发、长时间逐章/逐文件任务、pytest / build / CLI / 日志、本地数据库和文件系统、批处理、checkpoint / resume、执行—观察—修复循环；
- **混合任务**：只有当分工带来明确收益时才拆。不能为了“多模型协作”增加额外复杂度。

执行优先级：**操作简单与成功率 > 理论上的模型最优 > 过度细分工。**

## 6.7 基础模型创作能力优先，外部知识按需稀疏介入

AI-write 应优先发挥基础模型自身的综合创作能力。外部知识、BKP 和专业能力默认按需、稀疏、问题驱动地介入；只有真实创作问题暴露出明确知识缺口，且检索结果能提供额外价值时才调用。知识用于挑战、补洞、深化和边界提醒，而不是默认替模型搭建创作骨架。0 个知识命中/采用是合法结果。

## 6.8 新增能力必须证明边际价值

新增复杂能力必须证明边际价值；不能因为系统具备某项能力，就默认让所有任务经过它。

## 6.9 自由规划优先与 BKP 后置策略得到真实纵切支持

E2-B 真实长篇规划纵切验证：强模型自由规划优先原则继续成立——第一轮 0 张 BKP 即可形成可用长篇发动机；BKP 后置策略得到支持——Retrieval status=OK 时仍允许因为无独立增益而采用 0 张。

准确表述：本次 StoryPlan 案例没有召回真正有独立增益的 BKP，因此 `BKP_INDEPENDENT_VALUE = NO_USEFUL_BKP_AVAILABLE`；这不等同于“BKP 已证明没有价值”。

future planning 与 Canon 的隔离也真实通过：simulated writeback 的 `CANON_POLLUTION = ZERO`。

## 6.10 E2-B 保留的真实缺口

- `FREE_PLAN_QUALITY = PASS_WITH_RESERVATIONS`：P0 有轻度“策划委员会感”；初版父亲旧债存在“可拆除”问题；local relationship scope 说明该问题可通过更聚焦任务改善，但不能据此声称所有长篇规划质量问题已经解决。
- Retrieval 观察：当前检索对“责任 / 选择 / 后果”语义召回正常，但对“未解过去如何持续通过现在改变人物关系判断”的细粒度机制匹配不足。这是观察，不是现在重开 KnowledgeRetrieve / BookDistill 的理由。

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

> **参考作品学习链已经完成结构冻结；StoryDesign 运行底座与 StoryPlan 最小合同均已合入 main，StoryPlan 真实长篇规划纵切（E2-B）已通过并关闭（0-BKP 长篇发动机成立、局部 scope 成立、Canon 隔离零污染）；知识介入策略冻结为稀疏后置问题驱动；下一主线是 E2-C 局部重规划验证（尚未启动）。**
