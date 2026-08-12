# G4-A 最小创作合同 v0.1

> 状态：**G4-A 技术产物完成候选；当前仍停留在 G4-A，未自动进入 G4-B。**  
> 日期：2026-08-12  
> 对应 Gate：G4｜创作上下文与作者决策最小闭环  
> 上位边界：`00_项目控制/G4_启动记录_2026-08-12.md`、`00_项目控制/项目阶段门禁.md`  
> 目的：把成熟上游已经证明有价值的做法压缩成 AI-write 自己的**最小语义合同**，不是冻结最终文件格式、数据库或超级 Schema。

---

# 1. G4-A 到底要固定什么

G4-A 只固定五类概念工件之间的**语义、写入权、依赖关系和追溯关系**：

1. `Author Intent`；
2. `Story State / Canon`；
3. `Creation Brief`；
4. `Context Package`；
5. `Decision Record / State Diff`。

本阶段不固定：

- 最终数据库；
- 最终 JSON Schema；
- 最终 Markdown/YAML 模板；
- UI；
- Writer；
- Reader/Critic/Editor；
- 大型 KG / RAG / 向量库；
- 完整多 Agent 平台。

一句话：

> **先固定“什么东西算事实、什么只是任务、什么只是派生上下文、什么必须作者确认后才能写回”，再决定未来用什么技术承载。**

---

# 2. 五类工件的权威等级

| 工件 | 权威等级 | 主要写入者 | 是否可直接改变原创作品事实 | 是否可重建 |
|---|---|---|---|---|
| Author Intent | 作者权威 | 作者确认；AI 可提议修订 | 间接影响方向，不等于 Canon | 否 |
| Story State / Canon | 作品权威 | 只由已确认决策/已发生正文事实写入 | **是** | 否 |
| Creation Brief | 当前任务合同 | AI 根据作者请求 + 权威状态编译；作者可纠正 | 否 | 是 |
| Context Package | 运行时派生上下文 | Context Compiler | 否 | **是** |
| Decision Record / State Diff | 决策审计 + 写回事务 | AI 记录/生成；作者确认是写回门 | State Diff 应用后才是 | Decision Record 否；未应用 Diff 可重建 |

此外存在一个外部参考输入：

- **BKP / Book Knowledge**：参考作品知识资产；只作为启发、证据和比较材料。
- BKP **永远不是当前原创作品事实的权威来源**。
- 一个创作决定可以受 BKP 启发，但真正写入 Story State 的 authority source 应是“作者确认的决定”或未来“正文中实际发生的事实”，不是“某本参考书这么写”。

---

# 3. 三条硬隔离规则

## 3.1 BKP 与 Canon 隔离

允许：

```text
BKP Hit
→ 影响方案比较
→ 作者确认某个原创方向
→ Decision Record
→ State Diff
→ Story State
```

禁止：

```text
BKP Hit
→ 直接写入 Story State / Canon
```

例如《三体》的一个 Pattern 可以启发当前作品如何延迟信息，但不能因为被召回，就自动成为当前小说的世界事实、人物动机或未来剧情。

## 3.2 AI 推演与事实隔离

AI 生成的方案、预测、风险分析、未来分支，在作者确认前全部属于**候选**。

候选不得因为“模型很有把握”“多个上游都支持”“多数参考书都这样做”而升级成 Story State。

## 3.3 派生 Context 与权威状态隔离

Context Package 是一次任务的运行时快照，不是长期事实。

只要它依赖的 `Author Intent revision`、`Story State revision` 或 `Creation Brief revision` 发生变化，旧 Context Package 就必须视为 **STALE**，不得继续用于新的重大决策或写回。

---

# 4. 最小 ID 与版本关系

G4 暂不冻结具体命名格式，但语义上至少存在：

- `project_id`
- `intent_rev`
- `state_rev`
- `brief_id` + `brief_rev`
- `context_id`
- `decision_id`
- `diff_id`

最重要的依赖链：

```text
Author Intent @ intent_rev
+ Story State @ state_rev
+ Creation Brief @ brief_rev
+ Retrieval Package / BKP Hits
        ↓
Context Package @ context_id
        ↓
Decision Record @ decision_id
        ↓
State Diff @ diff_id (base_state_rev = state_rev)
        ↓
apply
        ↓
Story State @ state_rev + 1
```

如果决定同时改变作者当前方向 / Current Focus：

- Story State 用 State Diff 更新；
- Author Intent 自己生成新的 `intent_rev`；
- 两者共同引用同一个 `decision_id`。

**Author Intent revision 不是第六种工件，只是 Author Intent 的版本演化。**

---

# 5. Contract A｜Author Intent

## 5.1 作用

回答：

> **作者现在到底想写成什么？当前最在意什么？什么不能被系统擅自牺牲？**

它是作者方向的长期权威，不是“模型推测作者可能喜欢什么”。

## 5.2 v0.1 最小字段

### 必须有

- `project_id`
- `intent_rev`
- `work_direction`：这部作品想成为什么；允许自然语言，不要求复杂分类。
- `reader_promise`：当前最核心的读者承诺 / 希望读者长期得到什么。
- `current_priority`：作者当前阶段最在意的 1～3 件事。
- `current_focus`：当前故事段 / 当前 1～3 章主要关注什么。
- `hard_constraints`：明确不能破坏的方向、边界、题材/人物/表达约束。
- `avoidances`：作者明确不想要、厌恶或暂时禁止的方向。
- `open_space`：作者仍愿意探索、未决定的区域。
- `confirmation_ref`：最近一次作者确认该版本的记录或自然语言确认来源。

### 可选

- `target_audience`
- `tone_or_aesthetic_notes`
- `current_questions`

这些可选项只有真实任务需要时才加入，不因为“完整”而强制填写。

## 5.3 写入规则

- AI 可以根据聊天或已有决定**提议** Author Intent 修订。
- 只有作者明确确认的内容才能形成新的 `intent_rev`。
- “作者没有反对”不等于确认。
- AI 不得根据销量逻辑、参考书 Pattern 或自己的审美擅自改 `work_direction / reader_promise / hard_constraints`。

## 5.4 不应该放进 Author Intent 的东西

- 当前人物实时状态；
- 已发生事件流水；
- BKP Pattern；
- 大段参考书技巧；
- 每章全部计划；
- AI 自己推断出来、作者未确认的“真正主题”。

---

# 6. Contract B｜Story State / Canon

## 6.1 作用

回答：

> **这部原创作品现在“已经是什么样”，以及哪些未来安排已被作者确认但仍可修改？**

这里必须区分“已成事实”和“已确认计划”。

## 6.2 v0.1 最小内容

### 元数据

- `project_id`
- `state_rev`
- `last_decision_ref`

### 权威事实层

- `canon_facts`：世界规则、身份、地点、时间等已经成立的事实。
- `character_state`：人物当前欲望、认知、身体/资源/处境等对后续有影响的状态。
- `relationship_state`：关键关系当前状态及已确认变化。
- `occurred_events`：已经发生、后续必须承认的关键事件。

### 未闭合运行层

- `open_threads`：未解决悬念、伏笔、承诺、信息债、关系债等。
- `approved_plan`：作者已经确认的未来安排。

**`approved_plan` 不是 Canon。** 它是可修改的未来计划；作者出现更好灵感时可以推翻，但必须经过 Decision / State Diff 留痕。

### 最小 provenance

每个长期重要条目至少能追溯到一种 authority source：

- `author_decision:<decision_id>`；
- 未来 G4 之后可增加 `text_fact:<chapter/scene ref>`；
- 必要时 `manual_import:<source>`。

不得使用 `bkp:<...>` 作为 Story State 事实的 authority source。

## 6.3 写入规则

Story State 只允许两类正式来源：

1. 作者已经确认的创作决定；
2. 未来 Writer/正文真正产出后，经确认或可靠 Observer 提取的已发生事实。

G4 当前只有第 1 类。

AI 推测、Context Package、方案候选、BKP 知识都不能直接写入。

## 6.4 修正而不是静默删除

如果早期 Canon 被发现错误：

- 用显式 `correct / supersede` 方式修正；
- 保留原因和 Decision Record；
- 不静默删除旧事实，让未来无法解释为什么状态变化。

---

# 7. Contract C｜Creation Brief

## 7.1 作用

回答：

> **这一次具体要解决什么创作问题？**

它是当前任务合同，不是整个小说的缩小版。

## 7.2 v0.1 最小字段

- `brief_id`
- `brief_rev`
- `project_id`
- `scope`：当前是故事段 / 章 / 场景 / 人物决定 / 其他创作决策。
- `objective`：本次真正要解决的问题。
- `focal_entities`：本次最相关人物 / 关系 / 线索；只选必要项。
- `desire_and_obstacle`：相关时，主体人物当前欲望与主要阻力；不相关时可明确 N/A。
- `desired_reader_experience`：希望读者这一段经历什么变化，而不只是“发生什么剧情”。
- `inherited_obligations`：必须继承的 Canon / thread / approved plan 引用。
- `hard_constraints`：本任务不得违反什么。
- `freedom_zone`：哪些地方可以探索、变化、推翻旧设想。
- `knowledge_need`：希望从 BKP / 写作知识中获得哪类启发，用于 Retrieval。
- `assumptions`：AI 为了形成 Brief 做了哪些尚未被作者明确说出的假设。
- `source_versions`：至少记录 `intent_rev` 与 `state_rev`。

## 7.3 关于 assumptions

这是 G4 的重要安全字段。

禁止模型把推断偷偷写成作者要求。例如：

- 作者只说“这章有点闷”；
- AI 不能静默把任务改写成“必须加入打斗高潮”；
- 如果它认为“需要提升外部冲突”，必须写进 `assumptions / candidate interpretation`，让后续方案可以被拒绝。

## 7.4 写入规则

- Creation Brief 可以由系统根据作者当前请求自动编译。
- 它不是 Canon，不需要每次都要求作者填写表格。
- 如果系统发现作者请求与现有 Intent / State 有明显冲突，必须先暴露冲突，不能静默替作者选边。
- 作者修改 Brief 后生成新的 `brief_rev`，旧 Context Package 自动失效。

---

# 8. Contract D｜Context Package

## 8.1 作用

回答：

> **为了这一次任务，模型真正需要看到哪些少量信息？为什么是这些？**

它是运行时派生工件，不是长期事实库。

## 8.2 v0.1 最小字段

- `context_id`
- `project_id`
- `built_from`：`intent_rev + state_rev + brief_id/rev + retrieval_package_ref`。
- `selected_intent`：只取和当前任务有关的 Intent 项。
- `selected_story_state`：少量相关 Canon / character / relationship / thread / plan 条目，必须带来源引用。
- `selected_bkp_hits`：少量相关 BKP Hit，至少保留：
  - 作品来源；
  - knowledge id / 条目定位；
  - 为什么与当前任务相关；
  - scope / boundary；
  - confidence；
  - 必要 Evidence ref。
- `conflicts`：不同来源之间的冲突、互斥条件或张力。
- `gaps`：现有 Story State / BKP 无法可靠回答的地方。
- `selection_rationale`：为什么选这些、为什么没有全量塞入。
- `size_note`：至少记录条目数量；未来需要时再加 token 预算。

## 8.3 Context Package 不得做的事

- 不产生新的 Canon；
- 不把 BKP Pattern 改写成“本书必须遵守的规则”；
- 不隐去冲突只给一个漂亮综合答案；
- 不把全项目、全部人物、全部 BKP 塞进去；
- 不把“当前模型记得的聊天内容”当隐形输入。

如果某条信息很重要但没有进入权威工件：

> 先回到 Author Intent / Story State / Creation Brief 解决来源问题，而不是让 Context Package 偷偷保存长期记忆。

## 8.4 失效规则

以下任一变化发生后，旧 Context Package 必须 STALE：

- `intent_rev` 变化；
- `state_rev` 变化；
- `brief_rev` 变化；
- Retrieval Package 因查询或知识源变化需要重建。

STALE Context 可以留作审计，但不能继续驱动新的正式 State Diff。

---

# 9. Contract E｜Decision Record / State Diff

## 9.1 Decision Record 的作用

回答：

> **系统给过什么可能性，作者最后决定了什么，为什么？**

它是长期审计记录，避免半年后只看到结果却不知道为什么变成这样。

## 9.2 Decision Record v0.1 最小字段

- `decision_id`
- `project_id`
- `brief_id/rev`
- `context_id`
- `options`：1～3 个真正不同方向；每个方向至少包含：
  - `option_id`
  - `summary`
  - `why_fit_now`
  - `support_refs`：可同时引用 Story State 与 BKP，但必须区分性质；
  - `risks_and_tradeoffs`
  - `boundary_or_uncertainty`
  - `projected_state_impact`
- `author_action`：`choose / modify / reject_all / defer` 中的一种语义；具体枚举未来可调整。
- `final_decision`：作者真正确认的方向；如果是修改方案，以作者修改后的版本为准。
- `confirmation_ref`
- `state_diff_ref`：没有写回时可以为空。
- `status`：至少能区分 pending / confirmed / rejected / superseded。

系统可以提供“我更推荐哪一个”的建议，但必须明确标成 **AI recommendation**，不能伪装成客观最优或规则。

## 9.3 State Diff 的作用

回答：

> **这个已确认决定具体让作品状态变了什么？**

## 9.4 State Diff v0.1 最小字段

- `diff_id`
- `decision_id`
- `base_state_rev`
- `changes`：每一项包含：
  - 目标区域：canon / character_state / relationship_state / occurred_events / open_threads / approved_plan；
  - 操作语义：add / update / close / correct / supersede 等；
  - before（适用时）；
  - after；
  - reason；
- `impact_summary`
- `conflicts_or_warnings`
- `apply_status`
- `resulting_state_rev`（应用后）

如果已确认决定同时改变 Current Focus / Author Intent，则生成新的 `intent_rev`，并让它与同一 `decision_id` 关联。

## 9.5 写回门规则

### 作者未确认

- Decision 只能是 pending；
- 可以生成“预计影响”，但不能应用 State Diff；
- Story State 不变。

### 作者选择 / 修改并明确确认

- `final_decision` 成为正式决策；
- 系统生成 State Diff；
- 如果 Diff 只是作者已确认决定的机械展开，可以应用并留下审计；
- 如果 Diff 引入了作者没有确认的新解释、新剧情或新牺牲，必须再次向作者暴露，不能借“状态同步”偷渡新创作决定。

### 作者 reject_all

- 保存拒绝记录是允许的；
- **不得生成会改变 Story State 的 State Diff。**

## 9.6 乐观并发 / 旧状态保护

State Diff 只能在：

`base_state_rev == 当前 state_rev`

时应用。

如果不一致，说明状态已经被其他决定改变：

- 不自动硬套旧 Diff；
- 标记 conflict；
- 重建 Context / Decision / Diff。

这条规则不需要数据库也可以实现，但能防止旧对话或旧 Agent 覆盖新状态。

---

# 10. 一次完整 G4 决策的最小生命周期

```text
作者当前请求
        ↓
读取 Author Intent @ intent_rev
+ Story State @ state_rev
        ↓
编译 Creation Brief @ brief_rev
        ↓
KnowledgeRetrieve（只找少量相关 BKP）
        ↓
Context Compiler
        ↓
Context Package @ context_id
        ↓
提出 1～3 个差异方向
        ↓
Decision Record = pending
        ↓
作者：选择 / 修改 / 全部拒绝 / 暂不决定
        ↓
如果确认：final_decision
        ↓
State Diff(base_state_rev)
        ↓
安全检查
        ↓
apply
        ↓
Story State @ state_rev + 1
（必要时 Author Intent @ intent_rev + 1）
```

全链路中：

- BKP 从未成为 Canon；
- Context Package 从未成为权威事实；
- AI 未经确认的未来分支从未写回；
- 每次真正状态变化都可以追溯到一个作者确认的 `decision_id`。

---

# 11. 最小权限矩阵

| 动作 | AI 可自动做 | 必须作者确认 | 禁止 |
|---|---:|---:|---:|
| 从权威状态生成 Creation Brief | ✅ | 发现重大歧义/冲突时 | — |
| 从状态/BKP 生成 Context Package | ✅ | 否 | — |
| 提出 1～3 个方案 | ✅ | 否 | — |
| 推荐某个方案 | ✅，但必须标明是建议 | 否 | 伪装成客观规则 |
| 修改 Author Intent | 只能提议 | **✅** | AI 静默修改 |
| 修改 Story State / Canon | 只能生成 Diff | **✅** | 未确认直接写入 |
| 把 BKP Pattern 写入 Canon | — | — | **✅** |
| 作者拒绝全部方案后改变状态 | — | — | **✅** |
| 用 stale Context 生成正式写回 | — | — | **✅** |

这里的“作者确认”可以是自然语言确认，不要求作者手动操作复杂表单。

---

# 12. G4-B/C 以后最少需要的确定性校验

未来脚本只需要先检查这些机械事实，不承担文学判断：

1. 必需 ID / revision 是否存在；
2. `Context Package.built_from` 指向的 intent/state/brief revision 是否仍为当前版本；
3. Story State 条目的 authority source 是否合规；BKP 不能成为 Canon authority source；
4. BKP Hit 是否保留 source / knowledge id / boundary / confidence；
5. `State Diff.base_state_rev` 是否等于当前 `state_rev`；
6. 未确认 Decision 是否试图应用 Diff；
7. `reject_all` 是否错误产生状态变化；
8. `approved_plan` 是否被错误标成已经发生的 Canon；
9. 引用的 state/thread/entity id 是否真实存在；
10. apply 后 revision 是否单调递增、Decision Record 与 Diff 是否互相可追溯。

文学判断继续由 Agent / 模型 / 作者承担，脚本不制造“客观小说评分”。

---

# 13. Borrow-first 压缩结果

| AI-write 最小合同 | 主要借鉴来源 | 实际保留的思想 | 没有照搬的东西 |
|---|---|---|---|
| Author Intent | InkOS | author_intent、current_focus、作者确认后改变方向 | 完整运行时/界面 |
| Story State / Canon | InkOS、graphify-novel、NovelForge、ani-book | source of truth、可追溯状态、派生层可重建、确认后写入 | 大型 KG、全量数据库 schema |
| Creation Brief | AI-Novel、oh-story | 章节/场景任务合同、reader promise、欲望/阻力、净变化、期待/回报 | 自动导演、全套网文规则 |
| Context Package | InkOS + G3 KnowledgeRetrieve | protected/relevant context、少量 BKP、冲突/边界保留 | 超级 Context、全量长上下文 |
| Decision Record / State Diff | InkOS、creative-writing-skills、Apodictic、ani-book | 多方案探索、诊断 Firewall、作者确认门、可审计写回 | AI 自动替作者选方向、多 Agent 平台 |

因此 G4-A 没有发现需要新造一套大型底层系统的理由。

AI-write 真正需要自己定义的仍然只是：

> **五类工件之间的薄协议、版本关系、确认门、BKP/Canon 隔离和最小写回事务。**

---

# 14. v0.1 暂不冻结的实现问题

以下全部留给 G4-B/C 真实沙盒再决定：

- Markdown、YAML、JSON 如何分工；
- 是否每个实体一个文件；
- 是否采用单一 `state.md` 或分人物/关系/thread 文件；
- ID 最终格式；
- status 枚举最终名字；
- token budget 的具体数字；
- 是否需要轻量索引；
- 是否需要 Python validator；
- 哪些字段在真实创作中可以省略；
- 何时才值得引入数据库/KG。

当前默认倾向仍是：**人可读权威文件 + 可重建派生层 + 少量确定性校验。**

---

# 15. G4-A 自检结果

| G4-A 要求 | 结果 |
|---|---|
| Author Intent 最小字段 | ✅ |
| Story State / Canon 最小字段 | ✅ |
| Creation Brief 最小字段 | ✅ |
| Context Package 最小字段 | ✅ |
| Decision Record / State Diff 最小字段 | ✅ |
| 权威 vs 派生边界 | ✅ |
| BKP vs Canon 硬隔离 | ✅ |
| 作者确认门 | ✅ |
| provenance / trace | ✅ |
| revision / stale / base-state 防旧写覆盖 | ✅ |
| 没有冻结最终数据库或超级 schema | ✅ |
| 没有抢跑 G4-B/C/D、Writer、Reader、Retrieval 升级 | ✅ |

技术判断：

> **G4-A 的定义目标已经满足。当前应停在 G4-A，先让作者确认是否进入 G4-B；不得因为合同已形成就自动建立沙盒或写实现代码。**

---

# 16. 给 G4-B 的最小交接

如果作者确认进入 G4-B，下一步只需要在 `06_工作区` 建一个可丢弃原创故事种子，并用最简单的人可读载体实例化：

- 1 份 Author Intent；
- 1 份 Story State；
- 至少 1 个 Creation Brief；
- 后续为 G4-C 预留 `contexts/`、`decisions/`、`diffs/` 位置。

G4-B 的重点不是写好故事，而是验证：

> **一个新会话 / 新 Agent 只读取这些权威文件，是否就能准确知道作者想要什么、作品现在是什么，而不依赖旧聊天。**

在这件事证明以前，不进入 Context Compiler / Synthesis 实现。
