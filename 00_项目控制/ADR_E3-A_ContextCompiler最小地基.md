# ADR E3-A｜Context Compiler 最小地基

- 状态：**`E3-A implementation candidate / awaiting review`**（2026-08-15 提交；等待真实 GitHub diff 审查，不提前 PASS）。
- 范围：Phase E 的 E3-A；只做 Context Compiler 最小技术地基——“任务相关原创状态选择层”。不实现 Writer、Router、大型 RAG、embeddings、Vector/Graph DB、最终 Context Schema、最终 Canon Schema。
- 实现位置：`05_Skills与自动化/01_Skills/ContextCompiler/`（`context_compiler.py` / `test_context_compiler.py` / `SKILL.md` / `__init__.py`）。
- 证据：`06_工作区/E3A_ContextCompiler最小地基_2026-08-15/`（`validate_e3a_context.py`、`e3a_sandbox_result.json`、`final_report.md`）。

## 1. E3-A 目标

给定当前 task Brief、Author Intent、Story State，以及模型/Skill 对“当前任务需要哪些自身小说信息”的语义选择（可选少量 BKP），生成一个 `small / traceable / rebuildable / non-authoritative / stale-aware` 的 Context Package。核心转变：Story State 不再整包注入，而是只复制 semantic selection 明确点名的权威条目。

## 2. 冻结的设计决定

1. **runtime 不做文学相关性判断**。`AI = semantic brain；code = deterministic guardrail`。runtime 只做 ref 存在、来源真实、active/inactive、revision freshness、authority 隔离、provenance、dedupe、可重建性。
2. **Story State 精确选择，不整包注入**。`selected_story_state` 只复制 semantic selection 点名的权威条目（deepcopy 原始内容）；空 selection 合法，绝不 fallback 到全 State。
3. **selection 形式为 `area + id + reason`**。允许 area：`canon_facts / character_state / relationship_state / occurred_events / open_threads / approved_plan`；不支持任意 dict 路径。每个 selection 必须有非空 reason（可追溯）。
4. **确定性 ref 解析**。找不到 → ContractError；同 area 重复 id 歧义 → ContractError；同一 area:id 重复选择 → ContractError（不隐藏调用方错误）。approved_plan 用确定性索引构建：条目缺 id 或同 id 第二次出现 → ContractError（不静默取第一个/最后一个/dedupe），与 Canon area duplicate-id ambiguity 保持一致。
5. **approved_plan 只允许 active planning**。复用 StoryPlan `resolve_plan_activity`；已 superseded 的历史 planning 不进入 Context（保留 append-only history，不删除、不重实现 activity 算法）。
6. **production planning authority 可信性 + simulation 隔离**。默认允许 `author_decision:` / `manual_import:`（直接复用 StoryPlan 冻结常量 `TRUSTED_PLANNING_SOURCE_AUTHORITIES`，不另建白名单）；`simulation_author_decision:` 仅显式 `allow_simulation_sources=True` 的 sandbox/test 可用。`accepted_text:` 是合法 Canon authority 但不是合法 future planning authority，选入 approved_plan 必须拒绝。语义与 StoryPlan F2 一致；TEST_ONLY 状态不得流入未来 Writer Context。
7. **Intent 只复制真实存在的核心字段**。`work_direction / reader_promise / hard_constraints / open_space` 及可选 `current_priority / current_focus / avoidances`；不让模型伪造 Intent 值。
8. **BKP 复用冻结 E1 gate**。调用 E1 `build_context` 只提取 `selected_bkp_hits / retrieval / selection reason`，不重新实现 KnowledgeRetrieve，不修改 E1。
9. **BKP / Story State 结构隔离**。`selected_bkp_hits` 与 `selected_story_state` 永远两个独立区域；BKP 不获得 Canon authority、不覆盖 Story State、不伪装为原创事实。State 与 BKP 的张力只进 `conflicts_or_tensions`（`analysis_noncanonical`）。
10. **Context Package 非权威、零写回**。它是可重建派生工件，永不写回 Canon / Story State；构建过程对 State / Intent ZERO mutation。
11. **stale 语义完整**。`built_from = {brief_id, brief_rev, intent_rev, state_rev}`；`context_package_is_stale` 任一变化即 stale（比 E1 `context_is_stale` 多了 brief_id/brief_rev 检查），E1 helper 不改。
12. **不提前扩 Canon Schema**。条目要被确定性选择，当前必须有可寻址 id；不强迫所有 Canon item 有 id，不改 E1 `validate_story_state`。
13. **size_summary 只做可验证计数**，用于证明“确实发生了 selection，而不是把全部状态换个字段名打包”；不硬编码 token budget。

## 3. 明确不做

Writer；Router；大型 RAG；embeddings；Vector DB；Graph DB；semantic search over Canon；automatic Router；multi-agent context committee；Reader / Critic；State Writeback；token optimizer；context window model-specific packing；full dependency graph；最终 Context Schema；最终 Canon Schema；UI。

## 4. 验证方式

ContextCompiler 34 tests（真实最小 sandbox + 15 负例边界 + stale + 结构隔离 + planning authority/duplicate-id guard）；StoryPlan 50 tests 回归不变；StoryDesign 27 tests 回归不变。sandbox 验证 `selected_state_items (6) << total_state_items (26)`、空 selection 不 fallback 全 State、State/Intent ZERO mutation、BKP 与 Story State 结构隔离。**SIMULATED / TEST_ONLY 仅用于测试 gate，不得表述为作者已确认任何状态。**
