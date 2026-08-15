# ADR E2-C｜StoryPlan 局部重规划

- 状态：**E2-C-A implementation candidate / awaiting review**（不是 PASS；等待真实 GitHub diff 审查后才可能记录 `E2C_PASS` / `E2C_STORYPLAN_LOCAL_REPLAN_CLOSED`）。
- 范围：Phase E 的 E2-C-A；只做 accepted planning 的局部 supersede / stale / modify 边界验证。不实现完整 replacement engine、dependency graph、Context Compiler、Writer。
- 实现位置：`05_Skills与自动化/01_Skills/StoryPlan/`（`story_plan.py` / `test_story_plan.py` / `SKILL.md`）。
- 证据：`06_工作区/E2C_StoryPlan局部重规划_2026-08-15/`（`validate_e2c_local_replan.py`、`local_replan_sandbox_result.md`、`e2c_sandbox_result.json`）。

## 1. E2-C-A 目标

让已经进入 `approved_plan` 的某个局部 planning，可以被新的作者确认 planning **局部 supersede**，同时：旧 planning 作为审计历史保留；无关 sibling 与上层 ancestor 不受影响；Canon 完全不受影响；stale Brief 仍不能写回；`author_action=modify` 正常成立；不重算整本书。

## 2. 冻结的设计决定

1. **approved_plan 继续 append-only**。supersede 是追加携带 `supersedes` 的新条目，不是物理删除、不是原地修改。
2. **superseded 是 derived activity，不是存储状态**。旧 planning 不加持久 `status` 字段；当前有效性由纯函数投影 `resolve_plan_activity(state)` 从 `approved_plan` 重建（输出 active ids / superseded ids / 每个 superseded 的 superseded_by），非权威存储层，永不写回 Story State。
3. **supersedes 只允许显式、同 target 的局部替换，且必须由当前 Brief 显式引用**。写回 guard：每个 ref 必须真实存在于当前 `approved_plan`；不得自引用；列表内不得重复；被替换条目 `target_ref` 必须等于当前 Plan Brief 的 `planning_target.target_id`；且每个 ref 必须出现在当前 Brief 经过验证的 `planning_sources` 中（deterministic source binding）。same target 只是必要条件，不足以构成 replacement authority。
4. **replacement 可以 1→N；多 source Brief 支持 N→1 consolidation**。多条新 item 可同时引用同一 `supersedes` ref；若 Brief 显式引用多个 approved_plan source，则单条新 item 可同时 supersede 多个 active base。
5. **已 inactive 的 planning 不能再作为 replacement base，也不得作为当前已确认规划来源编译新 Brief**。v1→v2 之后 `v3 supersedes v1` 被拒绝；`compile_plan_brief(planning_sources=[v1])` 同样被拒绝；合法下一版是 `v3 supersedes v2`（沿当前 active 链尖前进）。旧 planning 保留在 append-only history 中，不删除、不写 status。
6. **sibling / ancestor 默认不受影响**。activity 投影只改变被显式引用条目的状态；未重算全书。
7. **built_from 不承担 dependency stale 传播**。它仍可能是 provenance 也可能引用 candidate / 规划来源，语义尚未稳定；不据此自动 stale descendant。
8. **full dependency graph / subtree invalidation / 递归失效传播 deferred**。E2-C-A 只处理显式 supersedes。
9. **Canon 永远不被 planning replacement 修改**。写回仍只有 approved_plan append + state_rev 增加 + last_authority_source 更新；E1 `apply_diff` 未改动；sandbox 验证 CANON_POLLUTION=ZERO。
10. **stale Brief 必须重新编译后才能写回**。局部 replan 期间 Story State 被任何合法 append 推进后，旧 Brief 因 `source_versions.state_rev` 不匹配被拒绝；基于新 rev 重编译的 Brief 让同一意图正常通过（sandbox 记录 STALE_REPLAN_BRIEF_REJECTED / RECOMPILED_CURRENT_BRIEF_PASS）。
11. **`simulation_author_decision:*` 不是生产可信 planning source**。生产可信 authority 只有 `author_decision:` 与 `manual_import:`；`compile_plan_brief` 默认拒绝 simulation authority。仅显式 `allow_simulation_sources=True` 的测试/sandbox 路径可以读取；TEST_ONLY planning 不等于作者确认。

## 3. 明确不做

最终 Plan Schema 设计；dependency graph engine；subtree replacement；built_from 自动失效；五层规划树；Context Compiler；Writer；UI；DB；Vector / Graph Store；新多 Agent 架构；E1 runtime 重构。

## 4. 验证方式

StoryPlan 测试保留 E2-A 全部 29 tests 并新增局部重规划测试（共 50 tests，含 F1 source binding 与 F2 simulation authority 隔离测试）；StoryDesign 27 tests 回归不变；disposable sandbox 走真实 Brief→Context→noncanonical Candidate→modify Decision（TEST_ONLY simulation）→Diff→apply 链。**SIMULATED_DECISION_ONLY**：本阶段所有 Decision 均为测试模拟，不得表述为作者已接受任何规划。
