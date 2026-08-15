# StoryPlan v0｜能力合同

## 目的

把作者已经确认或正在探索的故事方向，展开为可追溯、可修改、可局部失效的长篇 planning material。StoryPlan 不是大纲生成器，不把一句问题直接定成整本书章纲，也不把未来计划写成 Canon。

输入是作者的规划问题，例如“先规划前半程，我主要担心男女主太晚才真正站到对立面”“规划女主与母亲关系的中期推进”。Planning scope 自由：整本书、一卷、一段关系、一个悬念链、约 10 章、某角色路线、某个 open thread 都合法；不要求 book/volume/arc/chapter/scene 固定层级。

## 工件与权限

`story_plan.py` 直接复用 StoryDesign `story_runtime.py` 的确定性合同（authority、stale、project/ref 一致性、approved_plan-only writeback），只新增规划语义；它不理解文学质量。

每轮产生：

`Author Intent + Story State + 已确认规划来源 → Plan Brief → Context Package → proposal_noncanonical Plan Candidate → trace`

- Plan Candidate 一律 `proposal_noncanonical`；作者明确 choose/modify 后才创建 Decision Record，确认的 planning 只能 append 进 `approved_plan` 且 `occurred=false`。
- “第三卷计划让甲死亡”永远只是 planning；只有正文写到并被接受后，“甲已经死亡”才经 accepted_text / State Writeback 进入 Canon。
- 无已验证规划来源时，runtime 拒绝编译 Plan Brief——不假装已有作者方向。E2-A v0 的 planning source 只接受当前 Story State `approved_plan` 中真实存在的条目（ref 必须可查、`occurred` 非 true、authority 为 `author_decision:` / `manual_import:`）；直接 Decision ref 待未来有正式 Decision resolver/store 后再开放。

## 规划判断维度（模型判断，不是必填字段）

reader promise / reader expectation、人物欲望与选择、关系变化、冲突如何改变性质、suspense/information/reveal、promise/payoff、accumulated consequences、irreversible choices、open threads、阶段结束后故事为什么仍有动力。

## 模型执行提示

1. 强模型先基于 Author Intent、Story State、已确认 StoryDesign 与 planning target 自由规划；第一轮不默认注入 BKP。
2. 之后先诊断真实薄弱点（中段无推动力、关系长期不变、reader promise 长期不兑现、悬念拖太久、只有强度升级、角色长期缺席、缺少 irreversible choice 等）；只有真实问题暴露明确知识缺口才调用 KnowledgeRetrieve 或额外 stance。`NO_USEFUL_BKP` / `INSUFFICIENT_BKP` / 0 张 BKP 都是正常结果。
3. 作者未决定的死亡、背叛、谜底、关系归宿、最终反派、世界规则等保持 deliberate ambiguity；不为结构完整自动补成事实。
4. 不默认生成全书章纲、卷名、章数、高潮位点等固定结构；作者可见内容优先保留人物动机、关系变化和具体后果。
5. 专业 stance（character / reader / structure / continuity / research）只在具体缺陷触发时使用，不默认全开，不固化为多 Agent 流水线。
6. 把所有未来安排保留在 proposal，直到作者 Decision；局部重规划通过新 Decision + 携带 supersedes 的 planning 条目表达，不全书重算。E2-C-A 起 `approved_plan` 保持 append-only 历史：旧 planning 不删除、不原地改写、不加持久 status 字段；当前是否有效由纯函数投影 `resolve_plan_activity(state)` 派生（active / superseded / superseded_by），可随时重建，不写回 Story State。supersedes 写回 guard：ref 必须真实存在、与当前 Brief 同 target_ref、被替换条目必须仍 active（已失效条目不能再当 replacement base）、不得自引用/列表内重复，且 ref 必须出现在当前 Brief 经过验证的 `planning_sources` 中（deterministic source binding：same target 只是必要条件，不足以构成 replacement authority）；`compile_plan_brief` 同样拒绝已 inactive 的 planning source。replacement 允许 1→N；多 source Brief 支持 N→1 consolidation。`built_from` 仍是纯 provenance 元数据，不承担 dependency stale 传播（deferred，见 ADR E2-C）。
7. planning id 在当前 approved_plan namespace 内必须唯一（批次内不重复、不与现有 id 重名；supersedes 也必须使用新 id）；Brief writeback 同时受 intent_rev 与 state_rev 双 stale guard 约束。

## CLI

```powershell
python run.py --demo-dir C:\Temp\ai-write-storyplan-demo
```

该入口创建新的 disposable sandbox；已存在且非空的目录会被拒绝；它不读取或修改正式作品。
