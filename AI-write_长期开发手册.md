# AI-write 长期开发手册

> 更新日期：2026-08-13  
> 当前主线：**原著知识提取与蒸馏**  
> G5｜正文诊断与修订最小闭环：**PAUSED**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是一键自动写整本书。

长期目标仍是：

`参考作品知识 → 构思/规划 → 正文生成与修改 → 作者反馈 → 后台诊断/修订 → 状态维护`

当前不继续扩展写作闭环，先把“怎样从原著中可靠提取可长期调用的创作知识”研究清楚、跑稳定。

---

# 2. 当前主线：原著如何进入 BKP

当前固定的是**职责链**，不是 Skill 数量、Pass 数量或作者操作次数：

`SourcePrepare`
`→ 初步作品识别 / BookProfile 导航`
`→ 多个互补观察视角直接读原著`
`→ 按需 Developmental Deep Dive`
`→ BookDistill 总编辑式回源核证与收敛`
`→ 正式 BKP`
`→ KnowledgeRetrieve`

## 2.1 SourcePrepare：先把书识别和整理干净

SourcePrepare 只做输入标准化与来源识别，不做文学蒸馏。

它负责作品身份、版本/来源、完整性、章节边界与标准正文输入；只有 PASS 才进入后续分析。REVIEW/FAIL 才需要人工介入。

## 2.2 初步作品识别 / BookProfile：先知道这是什么书

进入深度蒸馏前，应先形成一个**导航性作品画像**：主要结构、阶段变化、题材/reader promise、显著强项、潜在强项、不确定项，以及后续应该把注意力放在哪里。

BookProfile 是导航，不是过滤器。它可以随着后续直接阅读不断修订，不能因为第一轮识别没看见某个维度，就提前宣布那个维度没有价值。

## 2.3 多视角 Discovery：直接读原著提取

重要观察视角应直接读取或回查原著，不依赖“先摘要再从摘要总结”的二手压缩链。

默认已有两个互补镜头，但它们不是固定蒸馏次数，也不是永久固定 Skill：

- **长篇运行 / 读者动力**：优先借 oh-story 与 AI-Novel-Writing-Assistant，观察故事发动机、阶段推进、期待/兑现、情绪生态、信息释放、人物/关系、跨章回收与追读动力；
- **Reader / Page Craft**：优先借 creative-writing-skills，观察逐时读感、人物心智可信度、POV、叙事距离、声音、句法、对话、潜台词、动作、感官、留白、微观机巧与组合效果。

作品需要更多互补视角时可以增加；某个视角明显无关时也不为了流程整齐机械跑满。Base Scan 的 MAP / Evidence / Observation / Boundary 属于这些阅读过程中的证据记录层，不需要单独再制造一次“全书蒸馏”。

## 2.4 Developmental Deep Dive：按问题触发

当初步识别或 Discovery 暴露出高价值、难解释或证据冲突的问题时，再进入专项深挖。可借 Apodictic 等成熟镜头研究 contract、Reader Experience、Decision Pressure、Scene Turn、Emotional Craft、Reveal Economy、Character Architecture、POV/Voice、Theme 等。

Deep Dive 次数不冻结；没有真实需要就不跑，有明显价值就可以多个。

## 2.5 BookDistill：总编辑式收敛

BookDistill 的核心职责不是“单枪匹马发现整本书全部精华”，而是把不同观察结果重新拉回原著：核证、去重、识别跨尺度组合效果、区分 Observation / Inference、降级过度抽象、补 scope / boundary / counterevidence / confidence，最后形成克制的 BKP。

---

# 3. 最终得到什么

BKP（Book Knowledge Package）是一部参考作品完成蒸馏后的长期知识资产。

作者默认只需要看到：

1. **BookProfile**：这本书在哪些创作问题上值得参考、主要强项/不确定项/已深挖方向；
2. **可检索 BKP**：未来写作时由后台按问题调用；
3. **简短完成报告**：来源、覆盖、深挖、校验和 Retrieval 可发现状态。

BKP 内部长期保存作品身份与 source fingerprint、作品地图、Observation、重要 Inference、Work-specific Pattern、Deep Dive 最终知识，以及对应 Evidence / scope / boundary / counterevidence / confidence。

逐章 evidence、manifest、Agent 工作记录和测试日志主要是后台审计材料。正常写作阶段只检索 BKP，不重新蒸馏原著。

---

# 4. 当前已有地基

- SourcePrepare v0.2.1：来源识别、只读标准化与章节输入；
- BookDistill v0.2：证据记录、多视角 Discovery、BookProfile、Deep Dive、总编辑收敛、BKP Finalize；
- 《一九八四》《三体》已完成真实 vNext 验证；
- KnowledgeRetrieve 已能加载正式 BKP。

这些证明了技术链能运行，但**还没有证明当前方法已经把原著中最值得学习的创作智慧提取得足够好**。当前研究重点就在这里，而不是先追求一个单体 Skill 或一键入口。

---

# 5. 当前开发/研究任务

当前优先回答：

1. 初步 BookProfile 怎样既能帮助导航，又不提前过滤未知价值；
2. 不同观察镜头怎样直接读原著、互补而不重复；
3. 长篇怎样按章/分块处理，同时保留跨章、跨卷、跨尺度效果；
4. 哪些发现值得触发 Deep Dive；
5. BookDistill 怎样把大量候选收敛成真正有长期调用价值的 BKP；
6. 用一部尚未蒸馏的新书跑完整链，检查真正漏掉了什么。

可以继续改造现有 Skill，也可以增加/复用多个流程或成熟上游实现。**当前不要求先做一个统一 orchestrator，也不要求作者只能一次操作。** 等提取方法稳定后，再决定是否把流程包装成一键体验。

---

# 6. 长期核心原则

## 6.1 Borrow-first

`真实问题 → 查成熟上游 → 能借就借 → 最小适配 → 真实运行`

当前私人项目中，许可证只做 provenance 记录，不作为技术路线阻塞。

## 6.2 案例只暴露问题，不决定架构

单本书的特殊问题不能直接升级成永久 Schema / Skill。

## 6.3 原著是最高事实源

重要观察必须能回到原著；BookProfile、BKP、Agent 推断都不能替代原著。

## 6.4 发现可以宽，最终 BKP 必须克制

允许多视角、跨尺度、未命名发现；最终只保留长期有调用价值、证据充分、边界清楚的知识。

## 6.5 单书不能证明普遍规律

单本 BKP 最高默认只到：

`Evidence → Observation / Inference → Work-specific Pattern`

Cross-book Pattern、Creation-tested Heuristic、Production Rule 属于后续阶段。

## 6.6 作者控制 ≠ 作者审批

后台机械工作默认自动完成，但“作者少操作”是产品体验目标，不是当前分析方法必须被压成单一步骤的理由。

---

# 7. 暂停的后续工作

G5 正文诊断与修订实验暂停。已有 G5 工件保留为历史证据，不继续要求作者阅读测试正文。

当前不继续 Writer / Reader / Critic / Editor / Controller、正文质量 Benchmark、UI、大型数据库、RAG/KG、多 Agent 平台或批量蒸馏全部素材。

---

# 8. 当前阶段完成标准

当前阶段不是“做出一个一键 Skill”，而是证明：

> **一部此前没有蒸馏的新书，经过来源识别、初步作品识别、多视角直接原著提取、必要专项深挖和总编辑收敛后，能够形成高质量、可追溯、可检索的 BKP；并且我们能清楚知道哪里提取得好、哪里仍漏。**

---

# 9. Git 与文档纪律

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

本地 dirty / untracked / stash 先识别内容再处理，不自动 pop/drop/clean，不为了普通同步建立无意义长期分支。

长期文档只留稳定原则和当前路线；具体过程放 `06_工作区` 和 Git 历史。

当前入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
专项目标：`06_工作区/原著提取与蒸馏_当前目标.md`。

---

# 10. 一句话总纲

> **当前先研究怎样把一本原著真正读懂、拆开、提炼并收敛成长期可调用的知识资产；流程可以多段、多 Pass、多 Skill，产品层的一键化以后再做。**