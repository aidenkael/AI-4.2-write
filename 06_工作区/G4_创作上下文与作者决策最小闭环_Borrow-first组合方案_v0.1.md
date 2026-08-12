# G4 候选｜创作上下文与作者决策最小闭环

> 状态：**提案，尚未正式立 Gate**  
> 日期：2026-08-12  
> 对应长期路线：Phase E｜创作核心后台  
> 前置状态：G3 已 `G3_RETRIEVAL_VALIDATED / CLOSED`  
> 原则：Borrow-first；先组合成熟上游，后写最小胶水；不直接开发完整创作系统。

---

## 1. 为什么 Phase E 不应该一次全部开发

Phase E 长期需要覆盖 Story/Project Bible、Canon/State、Context Compiler、Cross-book Synthesis、Planner、Writer、Character Sim、Reader/Critic/Editor、Continuity、State Writeback、Controller、Author Decision Loop。

如果一次把这些全部做成一个 Gate，风险是：

- 在没有稳定 Story State / Context 之前先做 Writer，后续上下文和状态协议返工；
- 把多个成熟上游重新自研一遍；
- 多 Agent / 多 Skill 先膨胀，作者反而变成系统操作员；
- 正文质量问题与状态/上下文问题混在一起，无法判断瓶颈；
- 还没有创作沙盒就冻结完整生产架构。

因此 Phase E 建议拆成多个小 Gate。第一个 Gate 只做后续所有创作模块共同依赖的“神经中枢”。

---

# 2. 建议正式 Gate 名称

## G4｜创作上下文与作者决策最小闭环

### 唯一核心目标

证明 AI-write 可以在**不依赖聊天记忆、不把整个项目/全部 BKP 塞给模型、不自动替作者做重大创作决定**的前提下，把：

```text
作者意图
+ 当前作品状态 / Canon
+ 当前创作焦点
+ 希望读者经历什么
+ 少量相关 BKP 知识
```

编译成一个小而相关的创作上下文，并进一步：

```text
提出 1～3 个可行方向
→ 说明各自依据 / 风险 / 冲突 / 边界
→ 作者选择 / 修改 / 拒绝
→ 只在作者确认后更新计划 / Story State
```

G4 **不负责证明正文已经写得好**。Writer、Reader/Critic/Editor 的完整生产闭环留给后续 Gate。

---

# 3. 为什么 G4 优先做这件事

G3 closeout 后两个明确未解决的系统性问题是：

1. **Cross-book Synthesis**：Retrieved knowledge 能找回来，但还没有根据当前作品情境综合成真正可用的原创方向；
2. **Author Decision Loop**：系统还没有形成“AI 推演 → 作者确认 → 状态写回”的正式运行闭环。

而这两件事共同依赖：

- 最小 Story/Project State；
- Author Intent / Current Focus；
- Context Compiler；
- 可追溯的状态更新。

所以先做这一层，比先做 Writer 更稳。

---

# 4. Borrow-first 组合方案

不是选一个项目整体照搬，而是让成熟上游各自负责最擅长的一段。

## A. InkOS —— G4 的主骨架参照

优先借：

- `author_intent`；
- `current_focus` / chapter intent；
- Context Compiler；
- protected / compressible context 思想；
- narrative forecast / 多未来分支；
- 分支对人物选择、风险、作者意图一致性的比较；
- 作者确认前不污染 Canon；
- plan → write → audit → state settlement 中的状态治理思想；
- “完成必须由真实文件/工具状态证明，不由 AI 口头宣布”。

AI-write 不需要照搬其完整运行时或界面。

## B. AI-Novel-Writing-Assistant —— 任务合同与长篇生产层次

优先借：

- 书 / 卷 / 章 / 场景的分层任务思想；
- Reader Experience Contract 中与当前任务相关的字段：核心问题、承诺回报、即时欲望、阻力、关键变化、情绪/信息变化、章末净变化、钩子责任；
- “规划、生成、验收、修复消费同一个合同”的思想；
- 状态回灌和长任务可恢复的工程边界。

G4 只借“当前创作任务怎么被表达清楚”，不启动自动导演或整本书自动生产。

## C. graphify-novel + NovelForge —— Story Bible / Canon 的数据纪律

优先借：

- source of truth 与派生索引/图谱分离；
- chapter → bible / state 更新；
- character / world / thread 的跨章状态思想；
- 结构化卡片 / schema / 上下文注入思路。

G4 不建设大型 Knowledge Graph，不先上数据库。先验证最小权威状态是否足够。

## D. ani-book-skill —— 权威文件与确定性校验

优先借：

- Markdown/YAML 等人可读权威工件；
- Python / 脚本只做确定性校验；
- 派生索引可重建；
- 作者确认后才进入长期事实。

目标是让项目状态不依赖某次对话或某个模型的隐藏记忆。

## E. creative-writing-skills —— 作者入口与探索方式

G4 只借：

- Muse 式作者入口；
- Brainstormer / Character Sim 等“探索多个可能，不提前替作者决定”的方法；
- 后台专业角色对作者隐藏的路由思想。

Writer / Reader Sim / Critic / Editor 全套生产环暂不在 G4 实现。

## F. Apodictic —— 决策诊断 Firewall

G4 只借：

- 指出问题、风险、解决方案类别；
- 不替作者写死具体内容；
- contract / reader promise / decision pressure 等用于比较创作方向的诊断镜头。

## G. oh-story —— 中文长篇读者动力约束

G4 只吸收进“创作任务合同 / 方案比较”的少量概念：

- 期待 / 回报；
- 压力 / 换气；
- 章节推进责任；
- 关系 / 信息 / 情绪净变化；
- 中文长篇的追读动力。

不在 G4 做完整网文 Planner / Writer。

---

# 5. G4 最小后台形态

G4 不冻结最终数据库或最终 schema，只验证下面五种**概念工件**是否足够。

## 5.1 Author Intent

回答：

- 这部作品现在想成为什么？
- 作者当前最在意什么？
- 哪些方向明确不想要？
- 当前 1～3 章 / 当前故事段的 focus 是什么？

## 5.2 Story State / Canon

只保存当前原创项目的权威事实和状态，例如：

- 已确认世界事实；
- 人物当前状态；
- 关系状态；
- 已发生事件；
- 当前悬念 / 伏笔 / 承诺；
- 当前计划中已确认部分。

**BKP 参考知识不得混入 Canon。**

## 5.3 Creation Brief

当前具体创作问题的任务合同，至少表达：

- 当前要解决什么；
- 主体人物当前欲望 / 阻力；
- 希望读者经历什么；
- 必须继承哪些已存在事实 / 承诺；
- 有哪些硬约束；
- 哪些地方仍允许自由探索。

## 5.4 Context Package（派生，不是权威事实）

Context Compiler 从权威状态中选择少量真正相关内容：

```text
Author Intent
+ Current Focus
+ relevant Canon / State
+ relevant Outline / Thread
+ Creation Brief
+ KnowledgeRetrieve 返回的少量 BKP Hit
→ Context Package
```

要求：

- 有来源；
- 有选择理由；
- 有 token/规模上限意识；
- 可重建；
- 不把整个项目和整个 BKP 塞进去。

## 5.5 Decision Record / State Diff

AI 输出 1～3 个方案后：

- 每个方案写清优势、风险、关键代价；
- 标记参考知识是“启发/证据”，不是规则；
- 作者可以选择、修改或全部拒绝；
- 作者确认前不更新 Canon；
- 作者确认后生成明确 state diff；
- 更新结果留下 Decision Record，可以知道“为什么变成现在这样”。

---

# 6. G4 建议子阶段

## G4-A｜把成熟上游压缩成最小合同

只回答：

- Author Intent 最少需要什么；
- Story State 最少需要什么；
- Creation Brief 最少需要什么；
- Context Package 最少需要什么；
- Decision / State Diff 最少需要什么。

不把每个上游原 schema 整包搬进来。

## G4-B｜建立一次性沙盒作品状态

在 `06_工作区` 建一个可丢弃的小型原创故事种子，仅用于验证后台。

不进入正式长篇，不把 `03_作品工程` 当试验场。

## G4-C｜Context Compiler + Cross-book Synthesis 最小原型

允许第一版非常轻：

- Markdown / YAML / JSON；
- Agent 语义选择；
- 少量确定性脚本；
- 直接复用 KnowledgeRetrieve；
- 不需要数据库 / 向量库 / KG。

验证：同一个创作问题能从 Story State + BKP 中组出小而相关的 Context Package，并提出 1～3 个有差异的方向。

## G4-D｜Author Decision Loop 验证

至少做几种真实决策：

- 选择一个方向；
- 修改 AI 给出的方向后再确认；
- 全部拒绝，要求重新探索；
- 作者临时偏离旧计划，系统说明影响后更新状态。

重点不是“AI 猜中作者”，而是作者始终能控制方向，同时系统能正确维护状态。

## G4-E｜收口判断

只判断这个最小神经中枢是否成立。

不因为它成立就声称 Writer / Reader / Critic 已经完成。

---

# 7. 建议最小退出条件

G4 只有同时满足以下条件才允许 closeout：

1. 有一个可丢弃原创沙盒，Author Intent、Current Focus、最小 Story State 可以被文件化保存，不依赖聊天记忆；
2. Canon / Story State 与 BKP 参考知识严格分离；
3. 一个 Creation Brief 能触发 Context Compiler，从项目状态和 KnowledgeRetrieve 中只选少量相关信息；
4. Context Package 可以说明信息来源和选择理由，且不需要全量塞入项目/BKP；
5. 至少对“偏人物 / 偏情节信息 / 偏读者体验”等不同创作问题验证情境化 Cross-book Synthesis；
6. 每次输出 1～3 个真正有差异的方向，而不是三个同义改写；
7. 每个方向说明：为什么适合当前作品、用了哪些参考知识、适用边界、主要风险/代价；
8. 作者可以选择 / 修改 / 全部拒绝，AI 不把多数意见或参考作品经验当成规则强推；
9. 作者确认前 Canon / Story State 不发生正式写入；确认后有明确 State Diff / Decision Record；
10. 作者偏离旧计划时，系统能先说明影响，再按作者确认更新计划/状态；
11. 重开新会话 / 新 Agent 时，只读权威工件即可恢复当前作品状态和最近一次重大决定，不依赖旧聊天；
12. 不修改 KnowledgeRetrieve，不升级 RAG/KG，除非真实验证出现阻塞性检索问题；
13. 项目控制文档、长期手册和 provenance 在 closeout 时同步；
14. 作者明确验收后才能退出 G4。

---

# 8. G4 明确禁止事项

- 不直接实现完整 Writer；
- 不直接实现完整 Reader Sim / Critic / Editor；
- 不跑正式长篇；
- 不把 `03_作品工程` 的正式作品当工具试验品；
- 不开发 UI / Obsidian 插件 / 独立客户端；
- 不建立大型数据库、Knowledge Graph、向量库；
- 不升级 KnowledgeRetrieve，只为“看起来更先进”；
- 不建立大型多 Agent 平台；
- 不把所有上游 schema 合并成超级 schema；
- 不因为一个沙盒就冻结最终 Canon schema；
- 不让参考书知识自动写入 Canon；
- 不让 AI 在作者确认前修改重大 Story State；
- 不让 Controller 自动替作者选择重大创作方向；
- 不把 AI-Novel 的自动导演整体照搬为 AI-write 产品哲学；
- 不因为 Phase E 很大就顺手做下一 Gate 的功能。

---

# 9. G4 之后才考虑什么

如果 G4 成立，后续 Phase E 才有稳定地基继续接：

```text
Planner / Outliner
→ Writer
→ Character Sim
→ Reader Sim / Critic / Editor
→ Continuity
→ Revision
→ 正文后的 State Writeback
```

这些模块都消费同一套 Author Intent / Story State / Creation Brief / Context Package，而不是各自重新发明上下文。

这样后续 Writer 或 Reader 能力即使替换上游，项目核心状态也不会跟着推倒重来。

---

# 10. 建议决策

建议正式建立：

> **G4｜创作上下文与作者决策最小闭环**

唯一核心目标：

> **让“作者意图 + 当前作品状态 + 少量跨书知识”第一次真正进入同一个可恢复、可追溯、作者可控的创作决策闭环。**

这一步完成后，再进入 Planner / Writer / Reader 等正文生产能力，比现在直接造“AI 写小说系统”风险低得多。
