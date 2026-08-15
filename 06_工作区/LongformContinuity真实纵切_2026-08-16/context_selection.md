# Context Selection｜第二轮 semantic state selection

> 状态：FROZEN（2026-08-16）。对象：`shadow_story_state.json`（state_rev=3，共 22 条目）。
> 纪律：只选本场真正需要的；不因担心漏信息而全选。本轮是第一次 shadow State 大于第一轮，selection 是否真实缩减为核心观察项。

## 选中（13 条）

| # | area:id | reason |
| --- | --- | --- |
| 1 | canon_facts:canon.seed.road | 四个月后旧路关闭，是周昌顺必须此刻算账的时间压力源 |
| 2 | canon_facts:canon.seed.debt | 旧债以融资/押金后果进入本场：周昌顺的账会算到宋宁的信用，宋宁的处境绕不开它 |
| 3 | canon_facts:canon.w1.thirdparties | 周昌顺、郑国栋的身份与利益是本场的直接素材 |
| 4 | relationship_state:rel.state.sisters | 本场要继续推动的关系轴：合作更必要与冲突更明显必须同时兑现 |
| 5 | character_state:char.state.songning.belief | 宋宁面对"姐姐方案赢"的结果时，旧判断会作为潜台词在场 |
| 6 | occurred_events:event.w1.public-admission | 冲突已公开化的既定事实：本场不得退回"大家还没说开"，且联运照旧是合作机器的存量 |
| 7 | occurred_events:event.w1.recalc-commitment | 宋乔的重算承诺以本场结果为触发条件，是她本场动作的依据 |
| 8 | occurred_events:event.w1.zhou-takeaway | 本场直接前情：两份方案都被周昌顺带走，他欠岛上所有人一个账 |
| 9 | occurred_events:event.w1.zheng-deadline | 郑国栋月底期限与"礼拜四来听账"都在本场兑现 |
| 10 | open_threads:thread.zhou.thursday-decision | 本场必须兑现的线：周昌顺的货量决定 |
| 11 | open_threads:thread.zheng.month-end | 未收线的外部时钟，决定本场结尾把压力交给谁 |
| 12 | approved_plan:plan.design.direction.island | 作者确认方向：每解决一个现实问题，合作更必要、冲突更明显；旧债进现实但不揭真相 |
| 13 | approved_plan:plan.e2b.simulated.first-half | P0 前半程规划义务来源（TEST_ONLY simulation gate；其义务已同时经 Brief inherited_obligations 传递） |

选中率：13/22 ≈ **59.1%**（另有 active plans 2 条中被选中 2 条）。

## 未选但可能相关的候选（逐条记录不选原因）

| area:id | 不选原因 |
| --- | --- |
| canon_facts:canon.seed.songning | 宋宁经营物流站的日常已由 recent prose 与 canon.w1.thirdparties 承载；本场无新增载荷 |
| canon_facts:canon.seed.songqiao | 宋乔归来与竞标的事实已被 event.w1.* 与 rel.state.sisters 覆盖，本场焦点是决定而非她的来历 |
| canon_facts:canon.w1.hailu | 海路方案三层结构上一场已完整展开；本场若复述条款即噪声，且易诱发重复上一场戏剧动作 |
| character_state:char.state.songqiao.stance | "物流站没有继续存在的价值"与本场决定无直接冲突面；选入反而可能诱导提前触碰"物流站命运"open space |
| occurred_events:event.w1.negotiation | 具体条款细节（八个点、最低量）本场不需要；语气已由 recent prose 保留 |
| occurred_events:event.w1.xiulan-urgent | 秀兰本场不出场 |
| occurred_events:event.w1.advice-appendix | "先看附页"指向旧债对账的后续线，本场不触发；提前选入会诱导埋伏笔 |
| open_threads:thread.songqiao.recalc-model | 与 event.w1.recalc-commitment 载荷重复，避免同一事实双份进场 |
| open_threads:thread.debt.reconciliation | 与 advice-appendix 同理，属后续场景线程 |

## BKP

0 BKP 起步（`knowledge_needs=[]`）；编译脚本内 retrieval 为 must-not-be-called 守卫。仅当 Review 暴露明确机制缺口时才按 `BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN` 后置考虑。
