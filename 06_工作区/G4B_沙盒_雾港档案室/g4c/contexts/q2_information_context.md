# Q2 Context Package｜情节 / 信息

`authority: derived_context_only`
`context_id: g4c-q2-information-v1`

## built_from

- `intent_rev=1`; `state_rev=1`; `brief_id=g4b-brief-001`; `brief_rev=1`。
- 原问题与实际运行 query 相同：一个异常档案的提交日期晚于人物死亡日期，怎样逐步释放信息和悬念，让每次揭示改变人物选择，同时不一次解释完谜底？
- Retrieval: `../retrieval/q2_information_raw.txt`（`status=OK`, 15 candidates）。

## selected_intent / selected_story_state

- Intent：信息逐步释放、不急于解释谜底；悬疑由人物选择推动。
- State：`canon.memory_package_metadata` 的可查元数据/不可随意查看内容；死亡后六个月提交是已发生异常；`thread.signature_validity`、`thread.submission_origin`、`thread.postmortem_date`；林舟须在上报、忽略、进一步查看间选择。

## selected_bkp_hits

1. 《三体》`deep_dive/dd_悬念.md`，Deep Dive Pattern `M2 信息不对称表`：按角色/组织/读者分层，逐级释放信息（scope/boundary/counterevidence/confidence 均为 `absent`）。
2. 《三体》同文件，Deep Dive Pattern `M4 命名不定义`：先给机制名称、延后揭示机制（同上）。

这是单书 Pattern Hypothesis，不是跨书定律；无 Evidence 字段由当前输出提供。

## why_selected / excluded_or_irrelevant

两条直接对应元数据异常、权限机制和“暂不解释”。`P9 统一回收点`属于远期结构闭合，当前场景不应承诺统一真相；资源死局、威慑和文明责任阶梯也超出场景尺度，排除。

## conflicts_or_boundaries / gaps

本题没有第二本真正相关的条目，故无真实跨书互补/冲突。`M2/M4` 的适用边界未在 BKP 输出中给出；当前只能作为待验证的单书借鉴。对“每一次揭示如何改变哀伤人物的具体选择”没有直接 BKP 支持，记为 `BKP gap: grief-linked reveal ladder`。

## synthesis / candidate_directions

1. **元数据阶梯**：先只给提交日期矛盾，再给“认证曾通过”的结果，最后才让林舟发现一条会决定是否上报的权限记录；每级只回答一个小问题并制造下一项选择。风险是把元数据堆成说明，须让每级都改变她能否/是否继续查。
2. **命名但不定义**：把异常标为既有制度术语（例如“死后提交复核”），让读者知道它可被处理却不知道机制；林舟为确认术语适用性做合规核验。风险是新术语若没有可见后果，会成为空名词。
