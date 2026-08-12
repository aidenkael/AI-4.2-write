# G4-E 收口验收

> 日期：2026-08-13  
> 结论：**PASS / G4 CLOSED**  
> 范围：只检查 G4-A～D 的退出条件、矛盾和尾巴，不新增架构。

## 1. 已验证链路

G4 已完成以下最小闭环：

`Author Intent + Story State + Creation Brief`
`→ KnowledgeRetrieve + 小 Context / Synthesis`
`→ 少量有差异候选方向`
`→ 作者自然语言反馈`
`→ Decision Record / State Diff`
`→ 合法计划写回或明确不写`

证据：

- G4-B：文件化 cold-read 恢复；
- G4-C：真实加载《一九八四》498 条 +《三体》653 条 BKP，人物/信息/读者体验三类问题均完成小 Context；
- G4-D：真实作者反馈形成 `g4d-dec-001`，`state_rev: 1 → 2`，只更新 `approved_plan`，Canon 未变。

## 2. G4-E 发现并解决的尾巴

### 2.1 revision 失效实际触发

G4-C 三份 Context 与 `brief-001` 都建立在 `state_rev=1`。

G4-D 写回后当前状态为 `state_rev=2`，因此：

- `q1_person_context.md`：STALE；
- `q2_information_context.md`：STALE；
- `q3_reader_context.md`：STALE；
- `brief-001.md`：historical / stale for future execution；
- G4-D 决策面：consumed / historical。

未来若继续该沙盒，必须从当前 revision 重新编译，不能复用旧 Context。

### 2.2 accepted_text mechanical settlement 边界

G4 的产品模型要求“作者接受正文后，明确事实由后台自动结算”，但 G4 又明确不提前实现完整 Writer。为避免假装 runtime 已完成，本阶段只做**非权威协议 dry-run**。

假设一段未来已经被作者接受的正文明确写出：

> 林昼没有打开记忆正文，只把这份异常档案标记为待复核，然后退出了内容入口。

协议判断应是：

- “未打开记忆正文”与“标记为待复核”是文本直接成立的事实，可形成 `mechanical_settlement` 候选；
- source 必须是实际 `accepted_text:<ref>`，而不是 BKP、Context 或 AI 推演；
- 若正文没有明确说明“她因此决定长期隐瞒”“系统一定会处罚她”等，不得自动推断写回；
- 明确机械事实无需作者逐条审批；
- 歧义、解释性结论或新的重大剧情必须转为 `ambiguous_inference` / `creative_change`。

本 dry-run **没有 authority，也没有修改当前 Story State**。它验证的是 G4-A 写回协议的分类与防偷渡边界，不证明生产级 Writer、Observer 或自动结算 runtime 已实现。

## 3. G4 退出条件审计

- 权威状态可文件化恢复：✅
- BKP / Canon 隔离：✅
- Context 小而相关、有来源：✅
- 人物 / 情节信息 / 读者体验均可情境化 Synthesis：✅
- 跨书不强造共识，gap 可显式保留：✅
- 作者可只用自然语言表达真实创作感觉：✅
- 真实反馈可形成可追溯 Decision Record：✅
- 重大创作决定保留作者 authority：✅
- future plan 与 occurred Canon 分离：✅
- reject / defer / ambiguity 不应写状态：✅（无 authority 分支测试）
- revision / stale / base-state 防旧写覆盖：✅
- accepted_text mechanical settlement 的协议边界：✅（non-authority dry-run）
- 无真实阻塞不升级 Retrieval/RAG/KG：✅

## 4. 明确不证明

G4 不证明：

- Writer 正文质量；
- 完整 Writer / Reader / Critic / Editor / Controller 工程链；
- 生产级 accepted-text 事实抽取与自动写回 runtime；
- UI / 数据库 / KG / 多 Agent 平台；
- BKP 已覆盖全部创作问题；
- 当前 Retrieval 是最终方案。

这些未来只有在真实创作执行任务出现时才验证，不能作为 G4 隐藏尾巴继续扩建。

## 5. 文档与 Git 收口

- 长期手册、当前索引、门禁、项目记忆、G4 记录、AGENTS 统一切为 G4 CLOSED；
- 不新增新的长期 taxonomy；
- 不为收口复制一批归档文件，Git 历史已保存旧状态；
- 本地 `stash@{0}` / untracked 属于本地 Git 保护状态，与 G4 逻辑关闭分离，不自动处理；
- 下一 Gate 未建立。

## 6. 最终结论

> **G4 正式关闭。已证明的是“可恢复创作状态 + 小 Context/跨书知识 + 作者自然语言决策 + 有边界状态写回”的最小中枢；未证明的 Writer/runtime 能力留给未来独立 Gate，不再拖在 G4 后面。**