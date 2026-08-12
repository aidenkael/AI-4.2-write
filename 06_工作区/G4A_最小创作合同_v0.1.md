# G4-A 最小创作合同 v0.1.1

> 状态：**G4-A 已完成；本文件是持续有效的最小合同，不再承担“当前阶段”状态提示。当前 Gate 以 `00_项目控制/当前工作索引.md` 为准。**  
> 日期：2026-08-12  
> 上位边界：`00_项目控制/G4_启动记录_2026-08-12.md`、`00_项目控制/项目阶段门禁.md`

---

# 1. G4-A 只固定什么

固定五类概念工件的语义、权威关系、版本关系和最小写回边界：

1. `Author Intent`；
2. `Story State / Canon`；
3. `Creation Brief`；
4. `Context Package`；
5. `Decision Record / State Diff`。

不冻结最终数据库、JSON Schema、UI、Writer、Reader/Critic/Editor、大型 KG/RAG 或多 Agent 平台。

---

# 2. 总原则：作者控制 ≠ 作者审批

作者主要通过：

- 给出方向/要求；
- 阅读 AI 正文；
- 用自然语言给出模糊或明确反馈；
- 接受、拒绝或继续修改正文；
- 对重大创作变化做决定；

来控制创作。

作者**不需要**逐条审批后台事实提取、状态表、Skill 路由或机械记账。

系统应区分三类写回：

### A. `mechanical_settlement`｜机械状态结算

作者已接受正文后，文本中清楚发生的事实可自动写回 Story State，例如人物移动、持有物、已知信息、清楚发生的事件、明确兑现/关闭的线索和文本直接成立的关系变化。

authority source：`accepted_text:<chapter/scene ref>`。

无需作者逐条确认，但必须可追溯、可校验。

### B. `creative_change`｜创作性变更

涉及作品承诺/核心方向、人物核心动机或重大关系走向、重要生死、世界基本规则、卷级/主线重大重规划，或与既有 Author Intent 明显冲突的改变时，AI 只能提议，作者明确确认后才写回。

authority source：`author_decision:<decision_id>`。

### C. `ambiguous_inference`｜歧义或推断

如果正文没有清楚成立，或 Observer 需要加入解释才能得到某个状态变化：不自动写回；标记候选/冲突；必要时询问作者。

**BKP、AI 推演和 Context Package 永远不能直接成为 Canon authority source。**

---

# 3. 五类工件的权威等级

| 工件 | 性质 | 主要维护者 | 是否可直接改变原创事实 |
|---|---|---|---|
| Author Intent | 作者方向权威 | 作者决定；AI 可提议 | 间接影响方向 |
| Story State / Canon | 原创作品权威状态 | 系统维护；来源必须合规 | 是 |
| Creation Brief | 当前任务合同 | 系统自动编译，作者可纠正 | 否 |
| Context Package | 可重建派生上下文 | Context Compiler | 否 |
| Decision Record / State Diff | 决策/结算审计 | 系统生成与记录 | 应用后改变状态 |

---

# 4. 最小 ID / revision

至少需要：`project_id`、`intent_rev`、`state_rev`、`brief_id + brief_rev`、`context_id`、`decision_id`（有重大决策时）、`diff_id`。

依赖变化后，旧 Context 必须 STALE。State Diff 只能基于当前 `base_state_rev` 应用，不能让旧会话覆盖新状态。

---

# 5. Contract A｜Author Intent

回答：**作者现在想把作品写成什么，当前最在意什么，什么不能被系统擅自牺牲。**

最小字段：`project_id / intent_rev / work_direction / reader_promise / current_priority / current_focus / hard_constraints / avoidances / open_space`。

AI 可以从对话中整理/提议修订；改变重大方向时需要作者确认。作者不需要填写表格，系统负责把自然语言转成该工件。

---

# 6. Contract B｜Story State / Canon

回答：**这部原创作品目前已经是什么样，哪些未来安排只是计划。**

最小内容：`project_id / state_rev / canon_facts / character_state / relationship_state / occurred_events / open_threads / approved_plan`。

`approved_plan ≠ Canon`：未来安排可以被作者推翻。

合法 authority source：`accepted_text:<ref>`、`author_decision:<decision_id>`、必要 `manual_import:<source>`。

禁止把 `bkp:<...>`、AI candidate、Context Package 作为 authority source。

---

# 7. Contract C｜Creation Brief

回答：**这一次具体要解决什么创作问题。**

最小字段：`brief_id / brief_rev / project_id / scope / objective / focal_entities / desire_and_obstacle / desired_reader_experience / inherited_obligations / hard_constraints / freedom_zone / knowledge_need / assumptions / source_versions`。

Creation Brief 默认由系统根据作者当前自然语言要求自动编译。`assumptions` 必须暴露 AI 自己补出的理解，避免把“这段有点闷”静默改写成“必须加打斗”。

---

# 8. Contract D｜Context Package

回答：**这一次任务真正需要看到哪些少量信息，为什么。**

最小字段：`context_id / project_id / built_from / selected_intent / selected_story_state / selected_bkp_hits / selection_reason / conflicts_or_tensions / size_summary`。

要求：小而相关；Story State 与 BKP 明确分区；BKP Hit 保留 source / knowledge id / scope / boundary / confidence；可重建；依赖 revision 变化后自动失效。

---

# 9. Contract E｜Decision Record / State Diff

## 9.1 Decision Record

只在真正存在创作取舍时发挥核心作用。

最小字段：`decision_id / brief/context ref / options / author_action / final_decision / confirmation_ref / status`。

`author_action` 可为：`choose / modify / reject_all / defer`。AI 可以推荐，但必须标成建议，不得伪装成客观最优。

## 9.2 State Diff

最小字段：`diff_id / base_state_rev / writeback_class / source_ref / changes / conflicts_or_warnings / apply_status / resulting_state_rev`。

应用规则：

- `mechanical_settlement`：来自已接受正文、事实明确、无冲突时可自动应用；
- `creative_change`：必须有作者确认的 `decision_id`；
- `ambiguous_inference`：不得自动应用。

任何 Diff 如果夹带正文没有成立的新解释/新剧情，都必须降级为 `ambiguous_inference` 或 `creative_change`，不能借“状态同步”偷渡创作决定。

---

# 10. 理想创作生命周期

```text
作者自然语言目标/反馈
→ 读取 Author Intent + Story State
→ 自动编译 Creation Brief
→ Retrieval + Context Compiler
→ Controller/Muse 路由相关专业能力
→ AI 生成或修改正文
→ 作者阅读：接受 / 再修改 / 拒绝
→ 接受正文
→ 自动提取明确事实并 mechanical_settlement
→ 如涉及重大方向，再走 Decision Record + creative_change
→ Story State 更新
→ 下一轮
```

作者不需要看到或维护大多数内部工件。

---

# 11. 最小权限矩阵

| 动作 | 默认 |
|---|---|
| 编译 Creation Brief | AI 自动 |
| 组装 Context Package | AI 自动 |
| 调用 Retrieval / 专业 Skill | Controller 自动 |
| 生成/修改正文 | AI 自动，作者看结果 |
| 从已接受正文提取明确事实 | AI 自动 |
| 明确事实的机械状态结算 | AI 自动，保留来源 |
| 重大创作方向变化 | 作者确认 |
| 歧义/推断型状态变化 | 候选/询问作者 |
| BKP 写入 Canon | 禁止 |
| stale Context / 旧 Diff 覆盖新状态 | 禁止 |

---

# 12. 机械校验

未来脚本只检查工程事实，不做文学评分：ID/revision 有效性、Context stale、Canon authority 合规、BKP 是否误写 Canon、`base_state_rev` 匹配、`creative_change` 作者确认、`mechanical_settlement` 的 accepted_text 来源、`ambiguous_inference` 是否误自动应用、`approved_plan` 是否误当已发生事实、apply 后 trace/revision 是否完整。

---

# 13. Borrow-first 压缩结果

- InkOS：Author Intent、Context Compiler、分支隔离、重动作确认；
- AI-Novel：任务合同、正文→审核/修复→状态回灌；
- creative-writing-skills：Muse 路由、作者不用手动调用技能、知识随故事维护；
- graphify-novel：`Write. Don't track.`、正文后更新 Story Bible；
- ani-book：渐进确认、只有验收内容进入长期记忆；
- Apodictic：诊断而不夺权；
- oh-story：中文长篇读者动力进入 Brief/方案判断。

AI-write 自己需要定义的仍只是薄协议、BKP/Canon 隔离、作者控制边界和最小写回规则。

---

# 14. G4-A 自检

- 五类工件最小语义：✅
- BKP / Canon 隔离：✅
- Author Control 与后台自动维护分离：✅
- accepted_text 可作为 Canon authority：✅
- 重大创作决定保留作者确认：✅
- 歧义/推断不自动写回：✅
- revision / stale / base-state 防旧写覆盖：✅
- 未冻结最终技术载体：✅

**结论：G4-A 合同已完成并持续作为后续 G4-B/C/D 的最小语义边界；当前阶段请读取 `当前工作索引.md`。**