# E2-C-A｜StoryPlan 局部重规划 sandbox 验证结果

> 执行者：Agent；验证脚本：同目录 `validate_e2c_local_replan.py`（disposable 内存状态，exit 0，`E2C_SANDBOX_OK`）
> 结构化输出：同目录 `e2c_sandbox_result.json`
> **SIMULATED_DECISION_ONLY**：全部 Decision 为 `author:TEST_ONLY/*` simulation，不得表述为"作者已接受任何规划"。

## 初始 sandbox 状态（state_rev=1）

- ancestor：`plan.book.direction`（target.book.direction）
- 待局部修改：`plan.rel.mid.v1`（target.rel.mid）
- unrelated sibling：`plan.suspense.mid`（target.suspense.mid）
- Canon：2 条 canon_facts + 1 条 character_state + 1 条 relationship_state

## 执行链与结论

| 步骤 | 结果 |
|---|---|
| v2 supersedes v1（author_action=modify，0 BKP，simulated Decision） | apply 成功，state_rev 1→2 |
| v1 保留与投影 | v1 原样保留且未被改写；投影 v1=superseded、`superseded_by=[v2]`；v2=active |
| ancestor / sibling | `plan.book.direction`、`plan.suspense.mid` 均保持 active → **LOCAL_REPLAN_ONLY_TARGET_CHANGED** |
| Canon | 五个 Canon 区域 apply 前后 deep-equal → **CANON_POLLUTION = ZERO**（全程保持到 state_rev=6） |
| cross-target supersede（supersedes=plan.suspense.mid） | ContractError（被替换条目 target_ref 与 Brief target 不一致） |
| missing ref（plan.not.exists） | ContractError |
| dead base（v1 已 inactive 后再 supersede v1） | ContractError（应 supersede 当前 active 最新版本） |
| 链 v1→v2→v3（v3 supersedes v2） | 通过；v1/v2 inactive、v3 active |
| 1→N replacement（v4a + v4b 同时 supersede v3） | 通过；`superseded_by[v3]=[v4a, v4b]`，两者均 active |
| stale 场景 | Brief A 编译于 state_rev=4 → 无关 sibling append 推进到 5 → Brief A 写回被拒（**STALE_REPLAN_BRIEF_REJECTED**）→ 基于 rev5 重编译 Brief B，同一意图通过（**RECOMPILED_CURRENT_BRIEF_PASS**），state_rev 5→6 |
| 持久 status/active 字段 | approved_plan 条目中不存在（activity 仅派生投影） |

## 最终 approved_plan（append-only history，9 条，含全部历史版本）

`plan.book.direction`、`plan.rel.mid.v1`、`plan.suspense.mid`、`plan.rel.mid.v2`、`plan.rel.mid.v3`、`plan.rel.mid.v4a`、`plan.rel.mid.v4b`、`plan.suspense.mid.extra`、`plan.rel.mid.v5`

最终 active：`plan.book.direction`、`plan.suspense.mid`、`plan.suspense.mid.extra`、`plan.rel.mid.v5`；
superseded：v1、v2、v3、v4a、v4b（superseded_by 见 JSON）。

## 说明

- built_from 未触发任何失效传播（deferred，见 ADR E2-C）。
- E1 apply_diff 未修改；写回仍只有 approved_plan append + state_rev 增加 + last_authority_source 更新。
