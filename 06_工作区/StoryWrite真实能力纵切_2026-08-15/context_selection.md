# Context Selection｜semantic state selection 记录

> 状态：FROZEN（2026-08-15，W0 写作前冻结）。
> 任务：写“姐妹第一次公开承认双方合理利益已经不能同时满足的谈判场景”。
> 基线：`author_intent.json` intent_rev=1；`story_state_after_simulated_writeback.json` state_rev=2。
> 策略：`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN` 第一轮 0 BKP；无 knowledge_needs，KnowledgeRetrieve 不得被调用。

## State 规模

- 总 State item 数：**9**（canon_facts 4 + character_state 2 + relationship_state 1 + occurred_events 0 + open_threads 0 + approved_plan 2）。
- selected State item 数：**9**。
- active planning（`resolve_plan_activity`）：`plan.design.direction.island`、`plan.e2b.simulated.first-half`（两条均 active，无 supersedes 关系）。

## 逐条选择与原因

| ref | 选入 | 原因 |
| --- | --- | --- |
| `canon_facts:canon.seed.road` | ✔ | 旧路关闭倒计时是本场谈判的直接压力源；第三方在场谈的正是关闭前的过渡安排。 |
| `canon_facts:canon.seed.songning` | ✔ | 宋宁经营的物流站是她要保住的谈判标的，也是宋乔方案要重新定位的对象。 |
| `canon_facts:canon.seed.songqiao` | ✔ | 宋乔代表区域公司竞标未来唯一大宗配送合同，是本场景对立方方案的事实基础。 |
| `canon_facts:canon.seed.debt` | ✔ | 旧债以融资难 / 现金紧的后果进入本场景（郑国栋的试探、宋宁的一瞬迟疑），是双方责任观分歧的载体。 |
| `character_state:char.state.songning.belief` | ✔ | 宋宁认定姐姐当年的离开与债有关：这层未问出口的旧判断支配她的防御、潜台词与对姐姐“切断责任”的警觉。 |
| `character_state:char.state.songqiao.stance` | ✔ | 宋乔坚持物流站没有继续存在的价值：这是本场景宋宁公开反驳的直接对象，也是她“不替妹妹留模糊空间”的内在逻辑。 |
| `relationship_state:rel.state.sisters` | ✔ | “不得不合作又越来越站到利益对立面”正是本场景要完成性质变化的关系轴。 |
| `approved_plan:plan.design.direction.island` | ✔ | 作者确认方向：每解决一个现实问题，合作更必要、利益冲突更明显；旧债持续进入现实选择但真相不揭。本场景必须同时兑现合作面与冲突面。 |
| `approved_plan:plan.e2b.simulated.first-half` | ✔ | 本场景是 P0 前半程的终点场景（第一次明确谈条件、第三方在场、公开承认不能两全）；planning obligation 直接来自它。注：authority 为 `simulation_author_decision:`，仅因本实验复用 E2-B 模拟工件，编译时显式开 TEST_ONLY gate（`allow_simulation_sources=True`）。 |

## 关于 9/9 全选的诚实说明

本 State 是种子态：只有 4 条 canon、2 条 character_state、1 条 relationship_state、2 条 active planning，occurred_events 与 open_threads 均为空；而本场景恰好是种子与 P0 规划的终点场景，因此逐条判断后全部承担载荷。**这不是“担心漏信息所以默认全选”**：每一条都给出了独立入选理由，空 selection 也不会 fallback，编译器层面不存在整包注入路径。真实观察：在种子态 State 上，“小上下文”的降噪优势无法体现；选择的价值要在 occurred_events / open_threads 积累之后才可测量——这一观察本身记入 postmortem。

## 未选择的重要候选信息

- State 内：**无**（State 全部 9 条均入选，理由见上）。
- State 外真实候选（编译器无法选择，属于规划提案而非 Story State）：
  - `P0_FREE_PLAN.md` 与 `local_scope_result.md`：`proposal_noncanonical`，不在 `approved_plan` 中。其义务以 Brief `inherited_obligations` 形式进入写作输入，而不是通过 Context Package。
  - 观察：local relationship planning 目前只有“工作区提案文件”这一存在形式；若它经作者确认进入 `approved_plan`，Context Compiler 就能像选 planning 一样选它。这是 STATE_WEAKNESS / 流程观察，不是本实验要修的代码 blocker（记录见 `context_postmortem.md`）。

## BKP

- knowledge_needs：`[]`；KnowledgeRetrieve 未调用（编译脚本内置 must-not-be-called 守卫）。
- 第一轮 BKP 数：**0**（`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN` 仍成立）。只有 W0 冻结诊断后发现明确写作机制问题且第二轮自由思考不足，才允许新增至多 1 个 knowledge need。
