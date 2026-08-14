# ADR E2-A｜StoryPlan 最小合同

- 状态：技术候选，feature branch 已 push，ChatGPT 首轮审查的两个权限 blocker 已窄修（planning source 真实可验证 + Decision 绑定当前 Plan Brief），等待复审；未 merge。
- 范围：Phase E 的 E2-A；不实现 Writer、StoryReview、完整 Context Compiler、完整 State Writeback、UI、DB、Graph、全局 Router 或固定多 Agent 平台。
- 实现位置：`05_Skills与自动化/01_Skills/StoryPlan/`。
- 上游核查记录：`06_工作区/E2A_StoryPlan上游核查与研究记录_2026-08-15.md`。

## 1. E2-A 目标

回答并落地一个最小合同：**已确认的 StoryDesign / approved_plan 如何在不污染 Canon、不锁死作者空间的前提下，被展开为可追溯、可修改、可局部失效、未来可重规划的长篇 planning material。** 只建合同与技术骨架，为 E2-B 的真实长篇规划纵切做准备；不做真实全书规划。

## 2. StoryPlan 不是 Canon

Plan Candidate 一律 `proposal_noncanonical`；确认后只能进入 `approved_plan` 且强制 `occurred=false`。例：「第三卷计划让甲死亡」永远是 planning；只有正文真正写到并被接受后，「甲已经死亡」才经 `accepted_text` / State Writeback 进入 Canon。模型补出的未来可能性全部保留 assumptions 非权威身份，deliberate ambiguity（死亡、背叛、谜底、关系归宿、最终反派、世界规则等作者未决项）不得被自动补成事实。

## 3. StoryPlan 不是最终固定层级大纲

不在 E2-A 把 book / volume / arc / chapter / scene 写成永久五层树，也不要求章数、卷名、高潮位点等必填字段。最小合同首先允许**规划任意一个 scope**：整本书、一卷、一段关系、一个悬念链、约 10 章、某角色中期路线、某个未解决 open thread。这些层级未来可用，但属于后续演进。

## 4. 复用哪些 E1 工件

直接 import 并复用 `StoryDesign/story_runtime.py`（零复制、零 E1 重构）：

- `validate_author_intent` / `validate_story_state` / `_require_same_project` 语义（经公开函数间接生效）；
- `build_context`：Context Package、stale 检查、0-knowledge-need 跳过检索、BKP 显式选卡与 provenance；
- `create_decision_record`：choose/modify 才获确认 authority，reject_all/defer 无 writeback；
- `make_planning_diff` / `apply_diff`：只 append `approved_plan`、`occurred=false` 强制、Canon 区域写禁、base_state_rev 与 project 一致性；
- `context_is_stale` / `mark_stale_if_needed`、`utc_now`、文件读写与 project 布局（plans/decisions/diffs/traces 目录沿用）。

## 5. 新增的最小语义

- **Plan Brief**（`artifact_type=plan_brief`）：project、source revisions、`planning_target {target_id, description, scope_kind, scope}`、`author_planning_question`（作者原话）、`planning_sources`（E2-A v0 唯一正式可验证来源是当前 Story State `approved_plan` 中真实存在、`occurred` 非 true、authority 为 `author_decision:` / `manual_import:` 的条目；未知 kind 与 proposal/context/bkp/ai_candidate 一律拒绝）、inherited_obligations、hard_constraints、`deliberate_open_space`、assumptions、knowledge_needs（允许空）。无已验证规划来源时直接拒绝编译——StoryPlan 不假装已有作者方向。直接 Decision Record（design_decision / author_decision ref）作为 planning source，待未来有正式 Decision resolver/store 后再开放；当前确定性来源使用 Story State 中已落地的 approved_plan。这是收紧合同，不是能力退化。
- **Plan Candidate**（`artifact_type=story_plan_candidate`）：`proposal_noncanonical`；模型规划内容作为 opaque `content`，runtime 不解析为 Canon facts；保留 brief_ref（含 rev）、context_ref、source_versions、planning_target。
- **Planning item 最小接口**：append 进 `approved_plan` 的条目要求 `id`、`description`、`target_ref`；允许 `supersedes` / `built_from` ref 字段；`occurred` 强制 false。
- **Decision → planning writeback 绑定**：`make_plan_diff` 除复用 E1 choose/modify + project 检查外，还要求 Decision 的 `brief_ref` 精确等于当前 Plan Brief 的 `brief_id@brief_rev`、Brief 与 State 同 project、且 Brief 的 `source_versions.state_rev` 等于当前 `state_rev`（旧 Brief 不得在新 State 上写回）。

## 6. 哪些 Schema 故意未确定

五层层级树与层级枚举；planning item 的内容结构；章纲/卷纲字段；dependencies 结构；supersede 的具体失效传播算法；最终存储形态。Plan Candidate 的 `content` 保持 provider-agnostic / opaque。

## 7. 局部重规划未来如何留接口

stable `id` + `target_ref` 已强制；`supersedes` / `built_from` 字段已允许；Plan Brief 记录 planning_target。作者未来说「第三卷不要这样走，前两卷保留」时，可只对 target_ref 指向第三卷的条目发起 supersede/replace，而不重算其它 target。E2-A 仅保存 `supersedes` / `built_from` 元数据，为以后局部重规划与失效传播留下接口；当前 runtime 不解释 `supersedes`，不会自动使旧 planning 失效，也不实现 dependency graph engine 或完整 subtree replacement。

## 8. BKP 后置稀疏原则如何继承

直接继承 `BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`：第一轮优先让强模型基于 Author Intent + Story State + 已确认 StoryDesign + planning target 自由规划；之后才诊断真实问题（中段无推动力、关系长期不变、reader promise 长期不兑现、悬念拖太久、只有强度升级、角色长期缺席、缺少 irreversible choice 等）；只有真实问题暴露明确知识缺口才调用 KnowledgeRetrieve 或额外 stance。0 BKP 正常；runtime 在无 knowledge_needs 且无选卡时完全不调用 Retrieval（E1 既有行为直接复用）。不默认注入结构卡/节奏卡/人物卡/读者卡。

## 9. 上游借鉴 provenance

只重新核查 E1 已确认的五个 pinned donor（详见研究记录），均为 concept-only，未复制代码或提示文本，未新增 donor：

| Repo | Pinned commit | 实际借鉴（E2-A 视角） |
|---|---|---|
| `haowjy/creative-writing-skills` | `fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3` | 作者原话保留、AI 建议与作者决定分开、未确认前保留 vagueness、不强制全书预规划。 |
| `Narcooo/inkos` | `8dee4cb2367ec40d986e9a69e4c3ec05e78e79a3` | future branch 与 Canon 分离、planning 非正史权限、revision/stale 机制。 |
| `ExplosiveCoderflome/AI-Novel-Writing-Assistant` | `3763cd11af4af379e935a655652e76fe98f7f6af` | plan → execute → feedback 阶段产物可恢复、局部更新概念；**拒绝**其 AI director 全自动产品哲学。 |
| `worldwonderer/oh-story-claudecode` | `0a34c6998263026ec6160320a89692cdaa53fe69` | 中文长篇读者期待、hook/payoff、阶段推进作为判断维度；轻上下文经验。 |
| `anotherpanacea-eng/apodictic` | `3fb7abcdde23915f302e020a29920069a3885fd5` | reader promise/reveal economy/pacing 作为诊断维度；诊断问题不替作者写死方案。 |

## 10. E2-A 不做什么

完整全书自动大纲、100 章计划、Writer、prose generation、StoryReview、完整 State Writeback、完整 Context Compiler、UI、DB、Graph、Vector Store、全局 Router、固定多 Agent pipeline、自动文学质量打分、五层 Schema 写死、大量新项目研究、复制平行 runtime、重开 apply_diff 非 blocker 技术债（除非 StoryPlan 复用形成直接风险——本轮未形成）。

## 11. 下一阶段 E2-B 的真实验证问题

用一个真实长篇规划纵切验证：已确认 StoryDesign 能否展开为有驱动力的前半程规划；deliberate ambiguity 是否真的被保留；0 BKP 与后置 BKP 在规划场景的实际表现；局部 scope（如一段关系的中期推进）规划是否可运行；作者 choose/modify/reject 后 approved_plan 是否准确且不污染 Canon；规划内容对作者是否可读、可改、可局部推翻。
