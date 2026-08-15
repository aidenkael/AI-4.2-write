# Context Postmortem｜正文反向检查 Context Compiler

> 状态：FROZEN（2026-08-15）。在 W0 冻结诊断与 W1 修订完成后反向判断。
> 结论先行：**CONTEXT_MISSING = 0；本次 W0 的所有问题均属执行层，无一可归因于 Context Compiler。**

## 1. Context 太少是否造成错误？

| 检查项 | 结果 |
| --- | --- |
| 事实错误 | 无。旧路倒计时、物流站、竞标、旧债四条 canon 使用全部正确。 |
| 人物状态错误 | 无。宋宁的旧判断、宋乔的立场均与 State 一致。 |
| 关系状态错误 | 无。“不得不合作又利益互斥”完整体现在场景结构中（散场后联运照旧 + 公开承认不能两全）。 |
| 遗漏 active planning obligation | 无。Brief 的 7 条 inherited obligations 逐条核验：谈条件而非谈父亲 ✔；第三方在场且必须知道货量归属 ✔；宋乔不替宋宁留模糊并把后果摆上桌面 ✔；宋宁不以“保住老客户”包装选择 ✔；不指责“不顾姐妹情” ✔；旧债只以后果进场、保留宋乔熟悉度的双解释 ✔；无爆炸式决裂、现实合作继续 ✔。 |
| 重复已发生事件 | 不适用（occurred_events 为空）。 |
| 错误关闭 open thread | 无。五项 deliberate open space 在 W0 / W1 均保持开放（W1 R3 新增 beat 严格停在“她相信／她问”）。 |

## 2. 有没有未选择的信息事实证明应该加入？

State 内无未选择项（9/9）。State 外存在一个真实观察：

- `P0_FREE_PLAN.md` / `local_scope_result.md` 是 `proposal_noncanonical`，不在 `approved_plan` 中，编译器无法选择。它们的义务本次通过 Brief `inherited_obligations` 与 `premise_bridge.md` 进入写作输入。
- 归类：**STATE_WEAKNESS / 流程缺口**（不是 CONTEXT_MISSING）。若 local relationship planning 经作者确认进入 `approved_plan`，Context Compiler 现有能力即可直接选择它，无需 Brief 手工搬运。StoryPlan 的合同能力（supersedes / active projection / stale）足以承载，缺的是使用路径，不是代码。

## 3. 选入 Context 的信息是否有噪声？

- 逐条使用度核验（以 W1 为准）：road / songning / songqiao / debt / sisters / 两条 active planning 均承担明确载荷；`char.state.songning.belief` 在 W0 中几乎未用、在 W1（R3）成为关键内心 beat；`char.state.songqiao.stance` 使用偏弱（并入方案的具体内容主要由 premise bridge 携带）。
- 结论：**无纯噪声**。两个观察记为经验而非缺陷：
  1. “被选中的条目”不等于“第一稿立刻用到的条目”——belief 是修订稿的核心，选择价值要在诊断后评估；
  2. 种子态 State 条目与 premise bridge 内容有重叠，当前 State 小、重叠成本为零；State 规模增大后，重叠治理属于 semantic selection 层的判断，不属于编译器职责。

## 4. W0 问题归因

| 问题 | 归因 |
| --- | --- |
| 宋乔个人赌注不可见（Reader-1 / Critic-2） | **WRITING_JUDGMENT**（P0 原文写过“她本人在竞标中的判断会受到质疑”，写作时未戏剧化；premise bridge 压缩时也只保留了“她需要提交模型”，属实验制备的次要因素 OTHER）。 |
| 宋宁旧判断缺位（Character-1） | **WRITING_JUDGMENT**（Context 已选入该条，第一稿未用，W1 补入）。 |
| “老周家的”指称不自然（Continuity-1） | **WRITING_JUDGMENT**（现场细节失误，与 State 无关）。 |
| “公开承认”缺未遂过程（Critic-1） | **WRITING_JUDGMENT**（规划提供了“再商量”老办法，第一稿写成摘要而非当场时刻）。 |
| 两处通用表达（Editor-1） | **WRITING_JUDGMENT**。 |

分布：CONTEXT_MISSING 0｜WRITING_JUDGMENT 5｜PLAN_WEAKNESS 0｜STATE_WEAKNESS 1（流程观察，未影响正文）｜REVIEW_DISCOVERY 0｜OTHER 1（bridge 压缩，次要）。

## 5. 对 Context Compiler 的总体判断

- 编译器按合同完成全部职责：逐条真实性 / active / authority（simulation gate 显式开启）/ stale 版本对齐 / 0 BKP 守卫 / 零 State mutation；运行输出与 `context_selection.md` 完全一致。
- 种子态 State 上 9/9 的选择率说明：精选的降噪价值要等 occurred_events / open_threads 积累后才可测量；本轮验证的是**安全性与可追溯性**（每条都有 reason，planning 义务无一遗漏），不是降噪比。
- 维持 `CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE`：本真实下游消费者未发现任何需要回改编译器的 blocker。
