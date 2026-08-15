# ContextCompiler

## 目的

把当前创作任务真正需要的**少量自身小说状态**与**少量 BKP**，编译成一个 `small / traceable / rebuildable / non-authoritative / stale-aware` 的 Context Package。ContextCompiler 不是大纲生成器，也不判断文学相关性——“这个人物事实是否值得选”“这个伏笔是否对本章重要”“这张 BKP 是否文学上最好”都属于模型/Skill 的语义判断。runtime 只证明：**模型选择的东西是真的、当前的、允许被放进上下文**。

即：`AI = semantic brain；code = deterministic guardrail`。

输入是当前 task Brief、Author Intent、当前 Story State、semantic state selection（模型/Skill 提供）、可选 selected BKP ids、可选 retrieval callable。不要求作者填写 Context 表格。

## 工件与权限

`context_compiler.py` 直接复用 StoryPlan / StoryDesign `story_runtime.py` 的确定性合同（authority、revision、approved_plan active projection、frozen BKP gate），只新增“任务相关原创状态选择层”。它不理解文学质量，也不修改 E1 / E2 frozen semantics。

每轮产生：

`Author Intent + Story State + Creation Brief + semantic selection → Context Package`

- Context Package 是可重建派生工件（`artifact_type = context_package`），永不写回 Canon / Story State；整体也不得成为任何 authority。
- `selected_story_state` 只复制 semantic selection 明确点名的权威条目（deepcopy 原始内容），不整包注入，也不用模型摘要替代原文；空 selection 合法，绝不 fallback 到全 State。
- `selected_bkp_hits` 与 `selected_story_state` 结构隔离；BKP 不能获得 Canon authority、不能覆盖 Story State、不能伪装为原创事实。State 与 BKP 的张力只进入 `conflicts_or_tensions`（`analysis_noncanonical`）。
- 允许的 selection area：`canon_facts / character_state / relationship_state / occurred_events / open_threads / approved_plan`。不支持任意 dict 路径。
- `approved_plan` 只能选当前 active planning（复用 `resolve_plan_activity`）；已 superseded 的历史 planning 保留在 append-only history 中，但不进入当前 Context。approved_plan 必须确定性可寻址：缺 id 或同 id 重复 → ContractError（不静默取第一个/最后一个/dedupe）。
- `approved_plan` 的 production authority 必须是可信未来规划来源：`author_decision:` / `manual_import:`（直接复用 StoryPlan 冻结常量 `TRUSTED_PLANNING_SOURCE_AUTHORITIES`，不另建白名单）；`simulation_author_decision:` 仅显式 `allow_simulation_sources=True` 的 sandbox/test 可用；`accepted_text:` 是合法 Canon authority 但不是合法 planning authority，选入 approved_plan 必须拒绝。
- `simulation_author_decision:` 的 planning 默认不注入；仅显式 `allow_simulation_sources=True` 的 sandbox/test 可用。TEST_ONLY 状态不得流入未来 Writer Context。
- 每个 selected State item 都对应一个可追溯的 `selection_reason`（`source_ref` + `reason`）；`reason` 必须非空，说明“为什么进入当前 Context”。

## 模型执行提示

1. 模型/Skill 根据当前 Brief 做语义判断，选出本任务真正相关的**少量** state 条目，每条给 `area + id + reason`；reason 要能回答“为什么这条信息进入当前 Context”。
2. runtime 只做确定性校验：ref 存在、来源真实、active/inactive、revision freshness、authority 隔离、dedupe、可重建性；不判断文学价值。
3. BKP 继续遵循冻结策略：无明确 `knowledge_needs` 时 0 张是正常路径；有需求时模型显式选择 id，runtime 只校验 provenance 与数量上限，不自动按排名注入。
4. Context 记录 `built_from = {brief_id, brief_rev, intent_rev, state_rev}`；任一变化即 stale，必须重建（`context_package_is_stale`，比 E1 `context_is_stale` 多了 brief_id/brief_rev 检查）。
5. 不预先扩 Canon Schema：一个条目要被确定性选择，当前必须有可寻址 id；若真实使用证明大量合法状态没有 id，再由 consumer evidence 决定是否升级 Canon contract，不现在提前扩 Schema。
6. `size_summary` 只做可验证计数（total/selected state items、active plans、BKP hits），用于证明“确实发生了 selection，而不是把全部状态换个字段名打包”；不硬编码 token budget。

## CLI

本轮不提供 `run.py`（暂无真实 CLI 价值）。测试入口：

```powershell
python -m unittest 05_Skills与自动化/01_Skills/ContextCompiler/test_context_compiler.py
```
