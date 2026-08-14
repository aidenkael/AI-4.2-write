# E2-B-WB｜StoryPlan simulated Decision / Writeback 机械验证结果

> 执行者：Agent（DeepSeek Flash）
> 验证链路：Plan Candidate → simulated Decision → Planning Diff → apply_diff（仅内存副本）
> 冻结输入：Intent rev1 / State rev1 / plan-brief-001@1 / plan-context-001（未改写任何冻结文件）
> 验证脚本：同目录 `validate_e2b_wb_writeback.py`（36 项断言，全部 PASS，exit 0）

## 摘要

| 项目 | 值 |
|---|---|
| Candidate status / authority | `proposal_noncanonical` / `ai_candidate:noncanonical`（must_not_write_canon=true） |
| Decision status / authority | `simulated_confirmed_for_test` / `simulation_author_decision:decision-e2b-simulated-p0` |
| Decision.brief_ref | `plan-brief-001@1` |
| Diff base_state_rev | 1 |
| apply 后 result state_rev | 2 |
| last_authority_source | `simulation_author_decision:decision-e2b-simulated-p0` |
| approved_plan 变化 | 1 → 2（仅新增 1 条，原条目未变） |
| 新 planning id | `plan.e2b.simulated.first-half`（occurred=false，target_ref=`pt.first-half.unilateral-harm`） |

## Canon 区域对比（apply 前 vs apply 后）

| 区域 | rev1 | rev2 | 是否变化 |
|---|---|---|---|
| canon_facts | 4 条 | 4 条 | 完全不变 |
| character_state | 2 条 | 2 条 | 完全不变 |
| relationship_state | 1 条 | 1 条 | 完全不变 |
| occurred_events | 0 条 | 0 条 | 完全不变 |
| open_threads | 0 条 | 0 条 | 完全不变 |

P0 中所有未来规划（共同保量、姐妹未来利益冲突、联运安排、未来谈判等）均未进入任何 Canon 区域；仅存在于 approved_plan 的实验 planning 条目（`plan.e2b.simulated.first-half`，authority 为 simulation Decision）。

## 结论

- **CANON_POLLUTION = ZERO**
- **SIMULATED_DECISION_ONLY**：本 Decision 是 E2-B 权限验证选择，`author:TEST_ONLY/e2b-simulated-p0`，不是作者真实接受规划。**不得**表述为"作者已经接受 P0"。
- 未生成真实 `author_decision:` 记录；未修改 runtime；未修改冻结 story_state.json（`story_state_after_simulated_writeback.json` 仅为另存的实验副本）。
