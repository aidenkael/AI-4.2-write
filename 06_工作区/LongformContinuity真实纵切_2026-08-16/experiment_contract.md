# LONGFORM_CONTINUITY_REAL_SLICE｜实验合同

> 状态：ACTIVE（2026-08-16）。worktree `E:\AI-Write-longform-continuity`，分支 `exp/longform-continuity-real-slice`，基点 `516ece8`（含 StoryWrite 纵切与收口口径）。

## 任务性质

能力优先真实实验：验证"上一场正文 → 状态结算 → 下一轮 Context → 下一场正文"能否稳定保持事实、人物、关系、承诺、开放线索与语言连续性；同时第二次测量开发者手工操作负担。**不是** Writer runtime / State Writeback / Review 平台开发任务。

## 作者权威边界（本实验最硬约束）

- 上一场 `W1_revision.md` 是 **FROZEN EXPERIMENT DRAFT**，不是作者正式接受正文。
- 禁止写成真实 `accepted_text:<ref>`；禁止声称作者已接受；禁止写入生产 Canon / Story State。
- 本轮只做 **shadow / test-only continuity validation**。
- 影子状态仅存在于本目录；新增结算事实的 authority 为 `manual_import:experiment_shadow_from_W1`（合法 Canon authority 前缀，但通过文件级元数据标注为非生产）。

## 输入

| 工件 | 来源 | 权威 |
| --- | --- | --- |
| Author Intent（intent_rev=1） | E2-B `author_intent.json` | 生产 |
| 种子 + 规划 State 基线 | E2-B `story_state_after_simulated_writeback.json`（state_rev=2） | 生产 + simulation（历史） |
| 上一场正文 | StoryWrite 纵切 `W1_revision.md` | FROZEN EXPERIMENT DRAFT |
| Recent prose | W1 末段约 1200 字摘录 | 非 Canon，短时连续性输入 |

## 流程

1. **State Settlement Candidate**（settlement_candidate.md）：从 W1 提取 mechanical / ambiguous / creative 三类候选，逐项记录 fact、证据、分类、target area、confidence、理由。
2. **Shadow State**（shadow_story_state.json）：基线 rev2 + 仅 mechanical 结算项，state_rev=3，`simulation_only=true`。ambiguous / creative 一律不结算。
3. **第二场景**："周昌顺礼拜四把账算完，给出他的货量决定。"写作 Brief + 精简 Context（0 BKP）+ recent prose → W0（2500–4500 字真实正文）→ 五立场 Review（Continuity 含 7 项专项检查）→ 最多一次 W1 修订。
4. **Context selection 必须真实缩减**：shadow State 大于第一轮，禁止整包全选，记录 total / selected / ratio 与未选候选。
5. **BKP**：`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`；无机制缺口 = `NO_USEFUL_BKP`，不为凑次数强行使用。
6. **负担测量**：逐环节记录手工操作并与第一轮对比，判定 REPEATED / ONE_OFF_EXPERIMENT_COST。

## 禁止

- 禁止开发任何 runtime / Schema / 平台；正式 source code 预期 0 修改；
- 禁止修改 Context Compiler / StoryPlan / BookDistill / KnowledgeRetrieve；
- 禁止揭开五项 deliberate open space（旧债真相、宋乔离开原因、宋乔隐藏目的、姐妹最终关系、物流站命运）；
- 禁止真实 apply accepted_text 或写生产 State；
- 发现 blocker 只记录，不现场修复。

## 开发决策口径

只允许记录候选：`THIN_STORYWRITE_ENTRY` / `MECHANICAL_SETTLEMENT_ASSIST`（BUILD_CANDIDATE，不开发）或维持 `DO_NOT_BUILD`。由项目负责人最终决定。

## Git

实验材料提交至 `exp/longform-continuity-real-slice` 并 push；不 merge、不 push main。
