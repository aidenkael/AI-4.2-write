# STORYWRITE 真实能力纵切｜最终报告

> 状态：FINAL（2026-08-15）。分支 `exp/storywrite-real-vertical-slice`，基点 origin/main `d7241c96`。
> 实验问题：当前已有基础设施能否真正服务一段小说正文写作？
> 一句话结论：**能。现有能力链（Intent → State → 真实规划 → Context Compiler → 强模型自由写作 → 立场诊断 → 修订）产出了一段可读、有人物个体性、无 Canon 污染的真实正文；零代码 blocker；唯一实测缺口是流程的开发者手工负担。**

## 实验量摘要

| 指标 | 值 |
| --- | --- |
| 正文规模 | W0 约 3000 字 → W1 约 3200 字 |
| Context | 9/9 State items（种子态全承担载荷，逐条 reason）；0 BKP；检索守卫未触发 |
| 五立场诊断发现 | 5 项真实问题（Reader 1 / Character 2 / Continuity 1 / Critic 1+Editor 同源措辞 2），无硬造 |
| W1 修订 | 5 处针对性修订（R1–R5），未重写整篇 |
| 问题归因 | CONTEXT_MISSING 0｜WRITING_JUDGMENT 5｜STATE_WEAKNESS 1（流程观察）｜OTHER 1 |
| BKP | `NO_USEFUL_BKP`（连续第三次 0-BKP 成立：E2-B、E3-A、本实验） |
| 正式 source code 修改 | 0 |
| Canon / Story State 写入 | 0；五项 deliberate open space 全部保持开放 |
| 负担判定 | `DEVELOPER_OR_AUTHOR_BURDEN_GAP = YES`（操作层）/ 作者认知负担 = 低 |

## 20 问

**1. 当前链条是否真的能支持一段可读小说正文？**
能。W1《同一批货》是一个完整场景：有第三方在场的公开谈判、双方各自付出代价的承认、未爆的决裂、继续运转的合作、带向前动力的结尾。全程只消费现有工件，没有新 runtime。

**2. W0 最大问题是什么？**
“双方都合理”只兑现了一半多一点：宋乔的个人赌注不可见（像公司代言人），宋宁对姐姐的旧判断没有内心在场；结构上“公开承认”来得太顺，缺一次“想用老办法含糊过去而不得”的未遂。全部属 WRITING_JUDGMENT。

**3. W1 是否明显改善？**
是。R1（未遂戏剧化）给了转折过程重量；R2（半拍停顿 + “重算的是她的判断”）让宋乔的代价可见；R3（门口老念头 beat）让宋宁的防御有了根源；R4/R5 消除一处不自然指称与两处通用表达。改善集中在人物深度与转折重量，结构未动——符合“针对性修订”定位。

**4. Context 是否漏关键约束？**
否。7 条 inherited planning obligations 逐条兑现；无事实/人物/关系错误；无 open thread 被错误关闭。CONTEXT_MISSING = 0。

**5. Context 是否有明显噪声？**
无纯噪声。`belief` 在 W0 未用、W1 成为核心 beat——选择价值需诊断后评估；`stance` 使用偏弱但非噪声（其具体化内容在 premise bridge）。种子态 State 与 bridge 的内容重叠在当前规模下零成本。

**6. 精选 Context 是否值得继续保留？**
值得，但理由不是本轮的降噪比（种子态 9/9，降噪无从体现），而是：逐条 reason 的可追溯性、active/authority/stale 守卫、以及杜绝整包注入的结构性保证。保留现状，不扩展。

**7. 是否真的需要 BKP？**
本场景不需要。五个问题全部可由一轮自由思考的针对性修订解决，不存在机制性知识缺口。`NO_USEFUL_BKP`。注意口径：这不证明 BKP 无价值，只说明本轮无独立增益需求。

**8. StoryPlan 对正文是否有帮助？**
有，且具体：规划提供了“第三方在场”“谈条件而非谈父亲”“无爆炸式决裂”“旧债只以后果进场”“两句基准台词的精神”等骨架，把冲突钉在具体利益上，避免强模型滑向“姐妹吵架”模板。局限同样真实：规划给“写什么”多于“怎么写”，E2-B 保留的规划质量 reservation 在本轮未被推翻也未被恶化。

**9. 人物是否保持个体性？**
W1 成立。宋宁：数字、名字、最坏打算、运单质感（“绕北线，晚一个钟头”“八个点，白纸黑字”）；宋乔：承诺边界语式（“承诺之外不是不做，是进价格”）、压平纸角、两点整。残余空间：宋乔语言整体偏均匀的职业化，靠细节而非词汇区分——可接受，记为后续场景的观察项。

**10. 是否有 Canon / continuity 错误？**
发现 1 处轻微 continuity 问题（“我跟老周家的说”当着本人指称其货），W1 R4 修正。无 Canon 冲突；时间线（公告后约八个月、距关闭四个月）与基线一致；五项 open space 全部保持开放。

**11. Review 哪种立场最有价值？**
Character 与 Critic 并列最有价值（分别找到人物根源缺位与转折结构问题）；Reader 确认了问题的读者可见形态；Continuity 找到 1 处小错（State 尚小，其价值会随 accepted_text 积累放大）；Editor 最轻。同一模型切换立场即可完成，**不需要五个独立 Agent**。

**12. 作者未来需要直接操作多少后台工件？**
应为 0。作者只需：一句话场景意图、阅读正文、反馈/接受。本实验的 10 个工件全部是开发者操作 → `DEVELOPER_OR_AUTHOR_BURDEN_GAP`（操作层）。积极面：作者认知负担本来就低，E1–E3-A 合同在“对作者隐藏复杂性”上方向正确。

**13. 当前最大的最终工作台能力缺口是什么？**
没有端到端的 StoryWrite 薄入口：能力全部存在，但“一句话 → brief → context → 正文 → 诊断 → 修订记录”需开发者逐件手工摇柄，且每个新场景重复。其次是 local relationship planning 缺少轻量批准路径（进入 approved_plan 后 Context 可直接选择，StoryPlan 合同能力已具备，缺的是使用）。

**14. 哪个缺口最应该下一步解决？**
优先不是开发，而是**再写一个场景**（建议：周昌顺礼拜四的算账结果）：让本场景正文成为 accepted_text，验证“前文自动成为下一场 Context 来源”，这是对链条真正的压力测试，也复验负担缺口的重复性。若第二场景重复同样手工成本，再启动缺口 A 的薄封装评估。

**15. 哪些东西明确不应该开发？**
Writer 平台、Writer Schema/DB/Router、multi-agent orchestration、Prompt framework、token optimizer、vector/graph DB、final Context Schema、State Writeback public API、Review/Revision 平台、E3-B 独立 Benchmark。本实验对它们没有暴露任何真实 blocker；五立场诊断用同一模型切换立场即够。

**16. 是否发现需要回改 StoryDesign / StoryPlan / Context Compiler？**
不需要代码回改。一个流程观察：local relationship planning 的批准使用路径（proposal → approved_plan）值得在真实创作推进中自然启用；Context Compiler 维持 `CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE`，本消费者未发现 blocker。

**17. 是否发现需要 Writer runtime？**
不需要。强模型直接写作 + 现有合同工件完成全部正文工作；runtime 层零技术 blocker。未来若开发，正当形态是薄流程入口，不是 runtime。

**18. 是否可以继续直接用强模型写作？**
可以，且这是当前证据支持的主路线：基础模型创作能力优先（6.8 原则）在正文层面再次成立，BKP 后置稀疏策略继续成立。

**19. 下一步最小行动是什么？**
由项目负责人决定。候选最小行动（不含任何新代码）：用同一案例写下一场景（周昌顺的礼拜四），把 W1 接受为该文的第一段 accepted_text（或按作者决定保留为非权威草稿），验证：① 前文如何进入下一轮 Context；② 手工流程成本是否重复；③ 人物声音在第二场景是否保持。

**20. 是否出现过度开发风险？**
本实验自身为零新增开发，无过度开发事实。风险在下一步：若用“建平台”方式弥合负担缺口，即是过度开发；应严格按 `CAPABILITY_FIRST_CONSUMER_DRIVEN` 与开发决策四条件执行。

## 能力缺口判断与开发决策

- 证据支持的选项：**H（当前基础能力已经够用，下一步只需继续更长真实创作）** 为主；**A（StoryWrite 需要薄能力封装）** 为唯一实测到的候选缺口（`DEVELOPER_OR_AUTHOR_BURDEN_GAP`），C/D 仅存在流程观察（local planning 批准路径），无代码诉求。
- 按开发决策四条件核验 A：①真实正文暴露问题 ✔（负担实测）；②重复或足够严重 △（仅一次实验，需第二场景复验）；③现有能力不能低成本解决 △（可人工摇柄，但每场重复）；④新代码明显降低负担 ✔（若为薄封装）。
- 条件②③未完全满足 → **本实验结论：DO_NOT_BUILD**。A 记录为“第二场景复验后的唯一 BUILD 候选”，其余一律 DO_NOT_BUILD。

## 附：本纵切同时完成的路线文档修正

`00_项目控制/当前工作索引.md` 与 `AI-write_长期开发手册.md`：NEXT_MAINLINE 改为 STORYWRITE_REAL_VERTICAL_SLICE；E3-B 独立 Context Benchmark 取消；新增 CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE 与 CAPABILITY_FIRST_CONSUMER_DRIVEN 长期原则；明确开发优先级（工作台能力 > 降低开发压力 > 子系统完整性）。未改动任何已有 ADR 的历史结论。
