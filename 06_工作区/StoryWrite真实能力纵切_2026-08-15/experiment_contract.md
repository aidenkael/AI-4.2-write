# STORYWRITE 真实能力纵切｜实验合同

> 状态：**ACTIVE**（2026-08-15）。
> 实验性质：disposable real capability experiment（能力优先真实写作纵切）。
> 分支 / worktree：`exp/storywrite-real-vertical-slice` @ `E:\AI-Write-storywrite-slice`（基点 origin/main `d7241c96`）。
> 本目录全部材料为一次性实验证据，不属于正式 Story State，不产生 Canon / `author_decision` 写入。

## 实验问题

> **当前已有基础设施（StoryDesign 方向 → Canon / Story State → StoryPlan 真实规划 → Context Compiler）能否真正服务一段小说正文写作？**

优先级：第一，最终 AI 写作工作台能力；第二，降低开发者长期维护 / 操作 / 决策 / 验证压力；第三，子系统工程完整性。

## 这不是什么

- 不是 Writer runtime 开发任务；
- 不是 Context Compiler benchmark（E3-B 独立 Benchmark 已取消，见路线修正）；
- 不是新架构建设任务。

禁止新增：StoryWrite runtime / Writer Schema / Writer DB / Writer Router / Prompt framework / token optimizer / vector DB / graph DB / multi-agent orchestration platform / final Context Schema / State Writeback public API。

## 冻结输入基线（复用 E2-B，不重新设计小说）

| 工件 | 路径 | 版本 |
| --- | --- | --- |
| Author Intent | `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/author_intent.json` | intent_rev=1 |
| Story State | `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/story_state_after_simulated_writeback.json` | state_rev=2 |
| 冻结种子 | `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/frozen_seed.md` | FROZEN |
| 真实长篇规划 | `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/P0_FREE_PLAN.md` | proposal_noncanonical |
| 局部关系规划 | `06_工作区/E2B_StoryPlan真实纵切_2026-08-15/local_scope_result.md` | proposal_noncanonical |

Story State 使用 rev=2（含 E2-B simulated writeback 的 P0 planning 条目），因此 Context Compiler 必须显式 `allow_simulation_sources=True`（TEST_ONLY gate）；这属于一次性实验复用模拟工件，不构成 production planning authority 松动。

## 写作目标

“姐妹第一次公开承认双方合理利益已经不能同时满足的谈判场景”（E2-B local relationship scope 第 5 段、P0 前半程终点的自然下游）。

要求：

- 真正写成小说正文（不是 planning / 梗概 / 剧本摘要 / 大纲扩写模板）；
- 规模 2500–5000 中文字，不为字数灌水；
- 五项 deliberate open space 全部保留：旧债真相、宋乔完整离开原因、宋乔隐藏私人目的、姐妹最终关系、物流站最终命运。

## 流程合同

1. 写作 Brief：使用现有最小合同能表达的信息，不开发新 Brief Schema（`writing_brief.md` + `creation_brief.json`）。
2. Context Compiler：模型做 semantic state selection，只选真正需要的条目，不因担心漏信息而默认全选；记录总量 / 选中量 / 原因 / active planning / 未选择候选（`context_selection.md` + `context_package.json`）。
3. W0：强模型自由写作。输入仅 Author Intent + Brief + Context Package + 必要前文衔接摘要；禁止输入整个 Story State / 全部 BKP / 全部 StoryPlan 历史 / Raw Discovery / 开发文档 / 测试结果（`W0_draft.md`）。
4. 五立场轻量诊断：Reader / Character / Continuity / Critic / Editor，每类只报 1–3 个真实问题，无明显问题允许 NONE，禁止为证明 Review 有价值而硬找问题（`W0_review.md`）。
5. BKP：只有 W0 冻结诊断后发现明确写作机制问题且第二轮自由思考不足才允许调用；最多 1 个 knowledge need、1–2 张有独立增益的 BKP；无有用卡记录 `NO_USEFUL_BKP`。
6. W1：针对性修订，记录根问题 / 改法 / 代价（`W1_revision.md`）。
7. 反向检查 Context Compiler：区分 CONTEXT_MISSING / WRITING_JUDGMENT / PLAN_WEAKNESS / STATE_WEAKNESS / REVIEW_DISCOVERY / OTHER，不把问题都归罪 Context（`context_postmortem.md`）。
8. 作者负担审查：`author_burden_review.md`；暴露时记录 `DEVELOPER_OR_AUTHOR_BURDEN_GAP`。
9. 最终报告回答 20 问（`final_report.md`），并给出 A–I 能力缺口判断与 DO_NOT_BUILD / BUILD 决策。

## 代码修改规则

正式 source code 预期 **0 修改**。发现代码 blocker 不现场修，只记录 `BLOCKER / 最小复现 / 影响 / 建议最小修法`，然后继续能继续的部分。不进入 F1 / F2 / hardening。

## 停止条件

完成 `final_report.md` 后停止。不自行开发 Writer / Review / Revision / State Writeback，不修 Context Compiler，不设计新 Schema，不创建 E3-B benchmark。下一步由项目负责人根据本纵切结果重新决定。

## 交付物清单

`experiment_contract.md` / `writing_brief.md` / `creation_brief.json` / `context_selection.md` / `compile_storywrite_context.py` / `context_package.json` / `premise_bridge.md` / `W0_draft.md` / `W0_review.md` / `W1_revision.md` / `context_postmortem.md` / `author_burden_review.md` / `final_report.md`
