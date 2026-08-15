# E3-A Context Compiler 最小地基 — 实验记录

> 状态：`E3-A implementation candidate / awaiting review`（不提前 PASS，等待真实 GitHub diff 审查）
> 日期：2026-08-15
> 基础：origin/main @ `1f6a56f`；隔离 worktree `E:\AI-Write-e3-context`，branch `feat/e3-context-compiler-foundation`

## 1. 交付

新增 Skill `05_Skills与自动化/01_Skills/ContextCompiler/`：

- `context_compiler.py`：`compile_context(...)` / `context_package_is_stale(...)` / `SELECTABLE_AREAS` / `CAPABILITY`；
- `test_context_compiler.py`：28 tests；
- `SKILL.md`、`__init__.py`。

新增窄 ADR：`00_项目控制/ADR_E3-A_ContextCompiler最小地基.md`。

Context Compiler public API：

- `compile_context(context_id, brief, intent, state, state_selections, conflicts_or_tensions, retrieval, selected_knowledge_ids, max_bkp_hits, allow_simulation_sources)` → Context Package；
- `context_package_is_stale(context, brief, intent, state)` → bool（brief_id / brief_rev / intent_rev / state_rev 任一变化即 stale，比 E1 `context_is_stale` 更完整）。

## 2. 核心语义

- runtime 不做文学相关性判断（`AI = semantic brain；code = deterministic guardrail`）；
- `selected_story_state` 只复制 semantic selection 点名的权威条目（deepcopy 原文），不整包注入；空 selection 合法，绝不 fallback 全 State；
- selection 形式 `area + id + reason`；area ∈ canon_facts / character_state / relationship_state / occurred_events / open_threads / approved_plan；不支持任意 dict 路径；reason 必须非空（可追溯）；
- approved_plan 只允许 current active planning（复用 StoryPlan `resolve_plan_activity`）；superseded 历史保留在 append-only history 但不进 Context；
- simulation authority 隔离：默认拒绝 `simulation_author_decision:`，仅显式 `allow_simulation_sources=True` 的 sandbox/test 可用（语义与 StoryPlan F2 一致）；
- BKP 复用冻结 E1 gate（调用 E1 `build_context` 只提取 selected_bkp_hits / retrieval / selection reason，不重新实现 KnowledgeRetrieve，不修改 E1）；BKP 与 Story State 结构隔离；
- Context Package 非权威、零写回；构建过程对 State / Intent ZERO mutation。

E3-A-R1 修复（2026-08-15，真实 diff 审查后）：approved_plan 改为确定性索引构建（缺 id / duplicate id → ContractError，与 Canon area duplicate-id ambiguity 一致）；production planning authority 白名单直接复用 StoryPlan 冻结常量 `TRUSTED_PLANNING_SOURCE_AUTHORITIES`（`author_decision:` / `manual_import:`），`simulation_author_decision:` 仅显式 gate 可用，`accepted_text:` 等非 planning authority 拒绝；Canon area authority 仍由 E1 `validate_story_state` 负责（`accepted_text:` 依旧合法 Canon source）。

## 3. 测试与回归

| 目标 | 结果 |
|---|---|
| ContextCompiler（真实 sandbox + 15 负例 + stale + 结构隔离 + planning authority/duplicate-id guard） | 34 tests OK |
| StoryPlan 回归 | 50 tests OK |
| StoryDesign 回归 | 27 tests OK |
| KnowledgeRetrieve 回归 | 4 tests OK |

15 负例边界全部覆盖：missing ref / duplicate selection / ambiguous id / unsupported area / superseded plan / simulation default reject / simulation explicit gate pass / BKP without knowledge_need / BKP not in retrieval / stale state_rev / stale intent_rev / changed brief_rev / Context zero State mutation / BKP 不进入 selected_story_state / empty selection 不 fallback 全 State。

## 4. 真实最小 sandbox（见 `e3a_sandbox_result.json`）

任务：“规划/准备写姐妹第一次公开承认利益已经不能同时满足的谈判场景。”

- Story State 共 26 条（8 canon_facts / 4 character_state / 3 relationship_state / 3 occurred_events / 4 open_threads / 4 approved_plan）；
- semantic selection 只挑 6 条：2 canon facts、姐姐当前状态、姐妹关系状态、1 open thread、当前 active 姐妹线 plan；
- `selected_state_items = 6 << total_state_items = 26`；`selected_active_plans = 1 / total_active_plans = 3`；
- superseded `plan.sisters-old` 保留在 append-only history，但不进入 Context；
- 空 selection → `selected_story_state = {}`，不 fallback 全 State。

## 5. 边界与不做

未修改 E1 `story_runtime.py`、StoryPlan `story_plan.py`、KnowledgeRetrieve、BookDistill。不实现 Writer / Router / 大型 RAG / embeddings / Vector/Graph DB / semantic search over Canon / multi-agent context committee / Reader / Critic / State Writeback / token optimizer / model-specific packing / full dependency graph / 最终 Context Schema / 最终 Canon Schema / UI。不 push main，不 merge。

**SIMULATED / TEST_ONLY 仅用于测试 gate；本阶段不构成任何作者确认，不自宣 `E3A_PASS`。**
