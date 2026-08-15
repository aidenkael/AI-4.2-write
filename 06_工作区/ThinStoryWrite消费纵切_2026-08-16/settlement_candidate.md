# Settlement Candidate｜scene2 W1 → shadow rev4（模型语义判断）

> 状态：FROZEN（2026-08-16）。输入：`../LongformContinuity真实纵切_2026-08-16/scene2_W1.md`（FROZEN EXPERIMENT DRAFT）。
> 纪律：只结算话语/动作本身，不结算含义；ambiguous / creative 永不写入。
> 消费方：`run_scene3_thin_chain.py` → `apply_settlement(mode="shadow", shadow_authority="manual_import:experiment_shadow_from_W2")`。

## mechanical（10 项，可写入 shadow State）

| # | 目标 | id / 操作 | 事实（话语动作本身） | 正文证据 | confidence |
| --- | --- | --- | --- | --- | --- |
| M1 | occurred_events | event.w2.zhou-decision / append | 周昌顺当众决定：他的大宗下个月起走海路拼线；宋乔的重算可以算，模型里有他这一份 | "我的大宗，下个月起走海路，拼线" | high |
| M2 | occurred_events | event.w2.three-party-condition / append | 周昌顺为走海路开出条件：岛上末梢、进岛的货由宋宁的站接，价格按明价写进合同，三方都签、缺一不行 | "岛上的末梢，进岛的货，阿宁的站接……三方都签，缺一不行" | high |
| M3 | occurred_events | event.w2.songning-three-day / append | 宋宁当众承诺：末梢的价格她要算，三天以内给周昌顺话 | "末梢的价格，我要算。三天以内给你话" | high |
| M4 | occurred_events | event.w2.songqiao-framework / append | 宋乔承诺：末梢计价和账期的框架明天中午以前送到站里，并陪宋宁对数字 | "末梢计价和账期，我明天中午以前给框架" | high |
| M5 | occurred_events | event.w2.zheng-month-end / append | 郑国栋接受"大宗跟着拼、末梢给宋宁"的安排，月底等价格与准话，并表示两人的准话他都记着 | "行。我月底等你们的价" | high |
| M6 | occurred_events | event.w2.xiulan-stocktake / append | 秀兰来消息：下礼拜店里盘点，两天的货都交宋宁；宋宁答复排得开 | "下礼拜我店里盘点，两天的货都给你，排得开吗？——排得开" | high |
| M7 | open_threads | thread.zhou.thursday-decision / replace_existing | 更新为已兑现：周昌顺礼拜四已当众给出决定（见 event.w2.zhou-decision 与 event.w2.three-party-condition），该线不再悬置 | 整场即该线的兑现 | high |
| M8 | open_threads | thread.songning.three-day-answer / append | 宋宁须在三日内算完末梢账并给周昌顺与宋乔准话（接或不接） | "三天以内给你话" + "你有三天。接不接，都给我一个准话" | high |
| M9 | open_threads | thread.contract.three-party / append | 三方末梢合同待成立：明价条款、三方签署缺一不行；未签前末梢安排不生效 | "价格按明价写进你们的合同……三方都签，缺一不行" | high |
| M10 | open_threads | thread.zheng.month-end / replace_existing | 更新：郑国栋月底等的是末梢价格与双方准话（指向 thread.songning.three-day-answer 与 thread.contract.three-party） | "月底等你们的价" | high |

## ambiguous（5 项，拒收，永不写入）

| # | 候选 | 拒收理由 |
| --- | --- | --- |
| B1 | 周昌顺"这一笔是我欠你的情分"＝他从此站宋宁一边 | 话语本身已结算（并入 M1/M2 场景）；"欠情分"的立场含义是解释，正文未定性 |
| B2 | 宋乔"钱没有名字"＝她对钱有超然/隐藏的金钱观 | 一句台词的含义推断；其动机归属 open space（隐藏私人目的） |
| B3 | 宋宁"姐姐对钱走的路太熟了"＝旧判断被强化 | belief 条目早已在 State（char.state.songning.belief）；本场只是再触碰，无新事实；含义方向属解释 |
| B4 | 周昌顺"最难的是算完了签字的人要认"＝预言签约冲突 | 格言式台词，非事实陈述；预言性含义不得预写 |
| B5 | 宋乔末梢框架"比宋宁现在跑的赚"＝宋乔在让利/做局 | 数字优劣的动机解释；直接触碰 open space 3（隐藏私人目的），拒收 |

## creative（2 项，拒收，永不写入）

| # | 候选 | 拒收理由 |
| --- | --- | --- |
| C1 | 宋宁最终接受（或拒绝）三方末梢条件 | 这是第三场的创作内容，提前结算即偷写未来场景 |
| C2 | 旧债与宋乔"对钱的路熟"存在因果关联 | 触碰 open space 1/2/3，属作者重大方向决定 |

## open space 核对

五项 open space（旧债用途、离开原因、隐藏目的、姐妹结局、物流站命运）在本结算中均未被触碰：所有 mechanical 项只记录谁说了什么、承诺了什么、期限是什么。
