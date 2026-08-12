# Q1 Context Package｜人物

`authority: derived_context_only`
`context_id: g4c-q1-person-v1`

## built_from

- `project_id: g4b-fogharbor-archive`; `intent_rev=1`; `state_rev=1`; `brief_id=g4b-brief-001`; `brief_rev=1`。
- 原问题与实际运行 query 相同：人物面对与已故亲人有关的异常证据时，怎样让内疚、回避和主动选择共同推动行动，而不是靠外部事件强推？
- Retrieval: `../retrieval/q1_person_raw.txt`（`status=OK`, 15 candidates）。

## selected_intent / selected_story_state

- Intent：人物反应重于设定说明；悬疑须由人物不得不做的选择产生；林晚官方已死亡，谜底未定。
- State：`character_state.lin_zhou` 的流程本能、未接姐姐最后来电的内疚与回避；`event.anomalous_package_arrived`、`event.postmortem_submission_date`；`thread.linzou_choice`；`plan.next_scene`（仅为可推翻计划，非已发生事实）。

## selected_bkp_hits

1. 《一九八四》`knowledge/observations.md`，人物 Observation：温斯顿在电幕前先摆出安详乐观的表情（evidence `chapters/0001.md#L29`；confidence 高）。此处可借的是“先展示自我保护动作，再让选择从该动作的失效中生出”，而非把林舟等同温斯顿。
2. 《一九八四》`knowledge/observations.md`，人物 Observation：温斯顿因身体上不能跑/动手而放弃袭击（evidence `chapters/0008.md#L203`；confidence 高）。此处可借“回避应落实为可观察的限制/动作”，不把抽象内疚直接宣告为动机。

两个条目的 scope / boundary / counterevidence 在 Retrieval 输出中均为 `absent`；它们都是单书 Observation，不是普遍规则。

## why_selected / excluded_or_irrelevant

两条都直接服务于“回避如何可见、选择如何由人物和制度共同逼出”。高排《三体》资源死局、文明开关、责任阶梯等条目尺度为文明/群体或连续主角，和本场的亲属内疚及小型制度选择不匹配，予以排除。

## conflicts_or_boundaries / gaps

没有需强行调和的跨书冲突；本题只有《一九八四》条目真正相关。BKP 未直接提供“亲属哀伤/内疚”机制，保留为 `BKP gap: grief-specific interiority`；不得以该 gap 推定林晚存活或谜底。

## synthesis / candidate_directions

1. **流程先行后失效**：让林舟先完成一次合规的异常登记/封存动作；其中一个确切元数据或权限提示触发她对“最后来电”的回避性身体动作，再让她选择暂不自动上报、先核验许可链。适合她的流程本能；代价是保留文件会增加违规暴露。
2. **回避也成为选择**：林舟准备将档案移交，却必须亲手确认提交者标记是否可被系统复核。她可选择关闭窗口（维持秩序）或查询仅限元数据的深层记录（承担后果），不打开记忆内容。适合当前 hard constraints；风险是若缺少可感知的私人触点，会显得只是流程题。
