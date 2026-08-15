# LONGFORM_CONTINUITY_REAL_SLICE｜Final Report

> 状态：FINAL（2026-08-16）。worktree `E:\AI-Write-longform-continuity`，分支 `exp/longform-continuity-real-slice`。
> 权威边界复核：本轮全部正文与状态均为 shadow / test-only；W1（两场）均为 FROZEN EXPERIMENT DRAFT；未使用 accepted_text authority；生产 Canon / Story State 零写入；正式 source code 零修改。

## 总判定

- **CROSS_SCENE_CONTINUITY_CHAIN = PASS_WITH_RESERVATIONS**：事实、人物、关系、承诺、开放线索、语言六项连续性在第二场均保持；reservation 是仍未获得真实作者 acceptance（闭环的最后一环只能由作者完成）。
- **CONTEXT_SELECTION_REAL_REDUCTION = PASS**：13/22（59.1%），首次真实缩减，且未漏关键项、无噪声。
- **STATE_SETTLEMENT_FEASIBILITY = PASS**：纯模型提取 + 分类纪律可完成，零结算错误进入正文。
- **DEVELOPER_OR_AUTHOR_BURDEN_GAP = REPEATED**。
- **DO_NOT_BUILD 维持**；两个 BUILD_CANDIDATE 记录在案（见 Q20）。

## 逐问回答

**1. 第一轮 StoryWrite 结论是否复现？**
复现。CURRENT_CHAIN_SUPPORTS_REAL_PROSE 继续成立；CONTEXT_MISSING 连续两轮 = 0；WRITER_RUNTIME_REQUIRED = NO；W0 问题仍主要属 WRITING_JUDGMENT；BKP 仍无调用条件。第一轮 reservation ①（未验证缩减价值）本轮已补上；reservation ②③（作者 acceptance、手工负担）分别保持原状与被证实。

**2. 第二场正文是否可读？**
可读。约 3100 字，戏剧动作完整（报账 → 决定 → 条件 → 三个期限），无灌水；周昌顺的账是本场的戏眼。

**3. 是否出现人物漂移？**
无实质漂移。宋宁克制、宋乔守时与"账式关心"、周昌顺"货是货情分是情分"、郑国栋短促现实均延续。唯一声音问题是守时句逐字重复（已 R3 修正为变奏）。

**4. 是否出现事实错误？**
W0 有 1 处事实精度问题（"每一票"过实，R1 修正）；W1 无事实错误。结算入 shadow State 的全部 mechanical 事实在第二场被正确使用，零错误。

**5. 是否错误重复上一场？**
无。没有第二轮条款交换、没有第二次公开承认；本场戏剧动作（第三方报账决定）与上一场不同构。7 项连续性专项全过。

**6. previous-scene facts 是否能可靠提取？**
能。从 W1 提取出 11 条 mechanical 事实、5 条被拒绝的 ambiguous 推断、0 条 creative change；每条有正文证据。提取本身无技术难度，难度在纪律（见 Q7）。

**7. mechanical / ambiguous 是否容易区分？**
主流容易，边缘需要纪律。"补不回来了"（B1）、"先看附页"（S10/B2）这类句子天然诱人往关系定性上解释；必须靠"只结算话语/动作本身、不结算含义"的硬规则压制。该规则本轮有效（第二场未偷用任何 ambiguous）。

**8. structured State 是否足以支撑下一场？**
足以支撑**事实与承诺层**（事件、期限、触发条件、关系轴），13 条 selection 覆盖本场全部事实依赖。**不足以支撑语气/意象/即时余波**——那部分由 recent prose 承担（见 Q9）。两者合起来才是完整答案。

**9. recent prose 是否有独立价值？**
有，且可指认：开场机器余波语气、秀兰急单日常化、红圈与"数灯"意象承接、宋宁心境延续，都不在 State 中。副作用 1 例（守时句逐字重复）。结论：简单 recent-text window（1000–2000 字）值得作为未来形态记录；**不需要全文 RAG**。

**10. Context selection 是否真实缩减？**
是。13/22 = 59.1%（第一轮 9/9 = 100%）。缩减来自真实判断：9 条未选项逐条给出不选理由（条款噪声、载荷重复、秀兰不出场、后续线程不提前埋伏笔等），且事后核对无一应选。

**11. 是否漏关键 Context？**
无。Review 与 postmortem 双重反向检查，CONTEXT_MISSING = 0。

**12. 是否存在 Context 噪声？**
无纯噪声。选入 13 条均在 W1 文本中承担可指认载荷；belief 条目再次呈现"W0 不用、W1 关键"模式（第一轮同），选择价值须以修订后文本评估。

**13. StoryPlan 是否仍有价值？**
有。`plan.design.direction.island` 在第二场继续约束"合作更必要 + 冲突更明显同时兑现"（末梢条件正是这个结构的第三次实现）；P0 义务经 Brief 通道传递仍有效。active projection 在 shadow State 上照常工作。

**14. Review 哪一类最有价值？**
本轮 **Continuity 专项 + Editor**：事实精度问题（"每一票"）与逐字重复都由它们抓到；Reader 抓到的"代价未被感知"是质量上限问题。Critic 本轮 NONE，说明结构层已在 Brief 阶段被约束住。

**15. W1 是否明显改善？**
是。4 处修订全部命中真实问题：事实精度、代价可感知、母题变奏、belief 在场；净增约 100 字，未伤结构。

**16. BKP 是否需要？**
不需要。连续第四次 0-BKP（E2-B、第一轮写作、本轮写作、本轮诊断）。`NO_USEFUL_BKP` 维持。

**17. open space 是否保持？**
保持。五项原 open space 无一被揭开；两项本场新增 open space（宋宁三天答复、郑国栋月底取向）在结尾保持开放；R4 措辞严格停在"她问不出口"。

**18. developer burden 是否重复？**
**REPEATED**，且新增两个场次线性环节（settlement、recent prose 截取）。详见 developer_burden_comparison。

**19. author burden 是否仍应接近 3 个动作？**
是。本轮没有任何一步要求作者理解 shadow authority / selection / state id；作者动作仍为：说想写哪一场、读正文、接受或反馈。第三动作（acceptance）恰恰是当前闭环唯一缺的真实环节。

**20. 当前最值得 BUILD 的候选是什么？**
两个候选均满足四条件的前三条（真实重复、无现有能力覆盖、薄形态）：
- `MECHANICAL_SETTLEMENT_ASSIST`：本轮增速最高、最易错的重复环节（读正文 → mechanical/ambiguous 分类 → 合规 State 更新）；
- `THIN_STORYWRITE_ENTRY`：一句话 → Brief → selection → compile → recent prose 的薄流程入口（两轮重复证据齐全）。
若未来只允许一个先行，证据更重的是 **MECHANICAL_SETTLEMENT_ASSIST**（线性增长 + 易错 + 直接决定 open space 是否被偷关）；两者可以同一薄封装的两条命令形态共存。

**21. 是否仍为 DO_NOT_BUILD？**
**是，本轮维持 DO_NOT_BUILD。** 任务合同要求候选只记录、不开发；且是否启动薄封装属于路线级决定，由项目负责人按 Q23/Q24 裁定。

**22. 是否需要回改已有子系统？**
不需要。Context Compiler / StoryPlan / StoryDesign / BookDistill / KnowledgeRetrieve 零修改、零回改需求；维持 CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE 与 StoryPlan 冻结。

**23. 下一步应该继续第三场真实创作，还是开始一个薄封装？**
给项目负责人的两条候选（本报告不裁定）：
- **A：写第三场**（宋宁三天内算末梢账并答复；月底郑国栋取向）。收益：把"正文 → 结算 → Context → 正文"跑成三连，验证 settlement 负担在第三场是否仍线性、State 增长后 selection 是否继续有效缩减；成本：再重复一轮全部手工。
- **B：第一次允许开发薄封装**（MECHANICAL_SETTLEMENT_ASSIST 优先，或含 THIN_STORYWRITE_ENTRY 的最小形态）。收益：从第三场起消除最重重复负担；风险：薄封装的边界必须在"只复用现有合同、不加新 Schema"的纪律下执行。
本报告的事实基础：连续性链条已两轮 PASS，缺口的证据也已两轮齐全——**继续实验的边际信息量在下降，消除负担的边际收益在上升。**

**24. 哪一种选择最符合"最终工作台能力第一、开发者压力第二"？**
若负责人接受"薄封装 = 复用现有合同的操作层、零新 Schema"这一形态约束，则 **B 更贴合两级优先级**：工作台能力的瓶颈已不在链条可行性（两轮证明），而在每场手工摇柄使真实长篇写作无法持续发生；开发者压力第二优先级也直接指向 B。A 仅在负责人认为"三连证据"对 acceptance 闭环仍有不可替代价值时优先。最终裁定权在项目负责人。

## 材料清单

experiment_contract.md / settlement_candidate.md / shadow_story_state.json / writing_brief.md / creation_brief.json / recent_prose_excerpt.md / context_selection.md / compile_scene2_context.py / context_package.json / scene2_W0.md / scene2_review.md / scene2_W1.md / continuity_postmortem.md / developer_burden_comparison.md / 本报告。
