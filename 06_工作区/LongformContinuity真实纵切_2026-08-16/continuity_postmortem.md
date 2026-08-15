# Continuity Postmortem｜跨场景连续性反向检查

> 状态：FROZEN（2026-08-16）。在 scene2_W0 冻结诊断与 W1 修订完成后反向判断。
> 结论先行：**structured State（13 条）足以支撑第二场的事实与承诺继承；recent prose 提供了 State 无法表达的短时连续性，两者职责不重叠。**

## 1. structured State 承载了什么（可指认）

| 第二场景中的效果 | 依赖的 State 条目 |
| --- | --- |
| 开场联运"照旧"与冲突不回退 | event.w1.public-admission |
| 周昌顺报账的合法性（他欠一个账） | event.w1.zhou-takeaway + thread.zhou.thursday-decision |
| 宋乔"重算可以算了"的触发 | event.w1.recalc-commitment |
| 郑国栋在场与月底压力 | event.w1.zheng-deadline + thread.zheng.month-end |
| 宋宁面对结果的潜台词（R4 beat） | char.state.songning.belief |
| "合作更必要 + 冲突更明显"同时兑现 | rel.state.sisters + plan.design.direction.island |
| 旧债只以后果在场、不揭真相 | canon.seed.debt + plan 义务 |

CONTEXT_MISSING = 0：Review 未发现任何"应选未选导致错误"的实例；未选的 9 条经事后核对确实未被正文需要。

## 2. recent prose 承载了什么（State 无法表达）

| 第二场景中的效果 | 只能来自 recent prose |
| --- | --- |
| "这台机器照旧在转——只是转动的声音比上礼拜轻"的余波语气 | 是 |
| 秀兰急单延续为日常（而非重提那一单） | 是 |
| 路线图红圈、"路灯数四个月"意象的承接与变奏 | 是 |
| 宋宁"难的是说出口以后"的心境延续 | 是 |
| 对话节奏与称呼习惯（周叔/阿宁/阿乔、短句） | 主要是 |

判断：这些全部属于**短时连续性**（语气、意象、即时余波、局部动作），不是事实。State 条目即使扩写也无法承载语气；recent prose 窗口（约 1400 字）恰好覆盖。**未来形态建议：一个简单的 recent-text window（最近一场末段，量级 1000–2000 字），不是全文 RAG。** 该建议只记录，不开发。

## 3. 结算质量反向验证

- mechanical / ambiguous 区分在写作端可验证：进入 shadow State 的 11 条 mechanical 事实在第二场全部被正确使用，零事实错误；
- 被拒绝结算的 5 条 ambiguous（关系破裂、宋乔知情、隐藏目的等）在第二场确实没有被正文"偷用"——W0/W1 未出现任何需要它们的效果；
- 这支持：结算层的严格分类直接决定了下一场能否不偷关 open space。

## 4. W0 问题归因

| 问题 | 归因 |
| --- | --- |
| "每一票"表述过实（Editor-1） | **WRITING_JUDGMENT**（与 State 无关；现场事实精度） |
| 周昌顺代价停在报数（Reader-1） | **WRITING_JUDGMENT**（Brief 已要求"决定必须有代价"，第一稿执行为陈述式） |
| belief 缺席（Character-1） | **WRITING_JUDGMENT**（Context 已选入；连续第二次第一稿不用该条——记录为稳定倾向，非 blocker） |
| 守时句逐字重复（Character-2） | **OTHER（recent-prose 副作用）**：逐字重复恰恰证明 recent prose 被强吸收；吸收本身是收益，副作用需要写作侧自觉变奏 |

分布：CONTEXT_MISSING 0｜STATE_SETTLEMENT_ERROR 0｜WRITING_JUDGMENT 3｜OTHER（recent-prose 副作用）1。

## 5. 对现有子系统的判断

- Context Compiler：第二次真实消费，selection 首次发生真实缩减（13/22 = 59.1% vs 上轮 9/9），编译零错误，维持 `CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE`，无回改需求。
- StoryPlan：`resolve_plan_activity` 对 shadow State 照常工作；planning 义务继续经 active plans + Brief 双通道传递，价值真实（见 final_report Q13）。
- State 结算：无 runtime，纯模型提取 + 分类纪律即可完成（可行性见 final_report Q6/Q7/Q12）；重复手工成本见 developer_burden_comparison。
