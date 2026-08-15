# Context Selection｜第三场（模型语义选择记录）

> 状态：FROZEN（2026-08-16）。编译结果：`context_package.json`（longform-ctx-003，status=CURRENT）。
> 规模：**total 30 / selected 14 / ratio 46.7%**（上一轮 13/22 = 59.1%）。
> State 从 22 条增长到 30 条后，selection 发生了更大幅度的真实缩减。
> BKP：0（无 knowledge need，`SKIPPED_NO_KNOWLEDGE_NEED`；BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN）。

## 选中（14 条，逐条理由）

| ref | 理由 |
| --- | --- |
| canon.seed.road | 四个月倒计时是末梢账所有数字的时间边界 |
| canon.seed.debt | 旧债只以信用/融资后果在场：宋宁垫资能力受限是本场的真实成本项 |
| canon.w1.thirdparties | 秀兰与郑国栋的身份利益在本场运转（日常单、月底时钟） |
| canon.w1.hailu | 宋乔框架（统一定价/账期/急单计价）是末梢对价的直接输入 |
| rel.state.sisters | 本场必须继续兑现：合作更必要与冲突更明显同时发生 |
| char.state.songning.belief | 连续两次第一稿缺席的条目；本场创作约束要求正面触碰 |
| event.w2.three-party-condition | 本场答复的直接对象：三方末梢条件原文 |
| event.w2.songning-three-day | 三天期限的出处，本场必须兑现 |
| event.w2.songqiao-framework | 宋乔框架中午送达是本场的第一个动作 |
| event.w2.zheng-month-end | 月底外部时钟：宋宁的答复必须给郑国栋一个取向 |
| thread.songning.three-day-answer | 本场必须收口的线 |
| thread.contract.three-party | 答复之后合同成立条件仍在前面，结尾必须保持开放 |
| thread.zheng.month-end | 月底期限本场不收，只被答复推进 |
| approved_plan: plan.design.direction.island | 作者确认方向义务（合作更必要 + 冲突更明显；旧债进现实不揭真相） |

## 未选（16 条，逐条理由）

| ref | 不选理由 |
| --- | --- |
| canon.seed.songning | 人物背景已由 belief + 全场视角承载，不需重复条目 |
| canon.seed.songqiao | 宋乔本场动作由 framework 事件承载，身份条目无新增用途 |
| char.state.songqiao.stance | 涉及"站已无存在价值"的旧立场，本场不重开该争论 |
| event.w1.negotiation | 条款细节是上一场的戏，本场只需要其结果（已由 w2 事件承载） |
| event.w1.public-admission | 公开化是既定背景，本场无新的公开承认动作 |
| event.w1.recalc-commitment | 重算已由周昌顺决定触发并进入宋乔框架，事件本体不再被引用 |
| event.w1.zhou-takeaway | 前情中的前情，本场无依赖 |
| event.w1.zheng-deadline | 已被 event.w2.zheng-month-end 与 thread 更新取代 |
| event.w1.xiulan-urgent | 上一场急单已日常化，本场不复述该单 |
| event.w1.advice-appendix | 附页忠告属对账线；本场没有对账动作，不提前埋伏笔 |
| event.w2.zhou-decision | 本场面对的是"条件"本身（three-party-condition），决定过程不再出场 |
| event.w2.xiulan-stocktake | 盘点单发生在"下礼拜"，时间上未进入本场三天窗口 |
| thread.zhou.thursday-decision | 已兑现线，不再进入当前执行 Context |
| thread.songqiao.recalc-model | 模型提交公司的后续本场不可见，不提前埋伏笔 |
| thread.debt.reconciliation | 对账线本场不动；旧债只经 canon.seed.debt 以信用后果在场 |
| approved_plan: plan.e2b.simulated.first-half | 本场无对应规划义务（TEST_ONLY 条目不选即不消费） |

## 事后核对承诺

写作完成后将逐条核对：未选 16 条是否有被正文实际依赖；若有，计 CONTEXT_MISSING。
