# Q3 Context Package｜读者体验

`authority: derived_context_only`
`context_id: g4c-q3-reader-v1`

## built_from

- `intent_rev=1`; `state_rev=1`; `brief_id=g4b-brief-001`; `brief_rev=1`。
- 原问题与实际运行 query 相同：怎样让读者从“工作异常”逐渐进入“私人刺痛 → 好奇 → 担心人物会付出什么代价”，同时保持悬念和情绪递进？
- Retrieval: `../retrieval/q3_reader_raw.txt`（`status=OK`, 15 candidates）。

## selected_intent / selected_story_state

- Intent 的 Reader Promise 是谜团每推进一步都更深入林舟与林晚未完成的情感关系；avoidances 禁止用“她很悲伤”代替反应。
- State：林晚官方死亡、林舟漏接最后来电；异常档案与死后提交日期；开放线索和“不可提前证明林晚活着”的约束。

## selected_bkp_hits

1. 《三体》`deep_dive/dd_悬念.md`，Deep Dive Pattern `M2 信息不对称表`：让读者、角色、组织拥有不同信息层，逐级释放（scope/boundary/counterevidence/confidence 均 `absent`）。
2. 《一九八四》`deep_dive/dd_情绪.md`，Deep Dive Pattern `F1 生理先行原则`：用可观察的身体反应给情绪刻度；该条是单书 Pattern Hypothesis，confidence 等字段均 `absent`。

## why_selected / excluded_or_irrelevant

前者支持“好奇”持续而不说明谜底，后者支持“私人刺痛”不靠情绪标签。Q3 高排的《三体》倒计时/统一回收/无意义外衣适于宏观悬念或长期反转，当前尚无可数期限或真实计划，排除；《一九八四》F2/F3 是终局型恐惧，强度和阶段不适合故事开端，排除。

## conflicts_or_boundaries / gaps

此处存在真实互补：`M2` 管信息位置，`F1` 管人物感受的呈现；它们不构成相互验证，也不应被合成普遍规则。两条都缺明确 scope/boundary，且没有直接覆盖“丧亲哀伤的渐进读者体验”，记为 `BKP gap: grief-specific reader arc`。

## synthesis / candidate_directions

1. **读者先看见代价线索**：读者从系统提示或值班规则知道一次深查会留下审计痕迹，林舟尚未读到该后果；随后以她的具体回避动作连到姐姐。优点是担心来自选择代价；风险是信息差若过大，会削弱与林舟的同步。
2. **角色先感到私人刺痛**：先让林舟对日期/身份标记产生克制的身体反应，再只拿到一个可验证但不解释原因的小结果；读者与她一起追问。优点是情感和好奇同源；风险是没有外显后果时悬念可能变成纯回忆。
