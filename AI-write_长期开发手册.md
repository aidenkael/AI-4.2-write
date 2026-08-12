# AI-write 长期开发手册

> 更新日期：2026-08-13  
> 当前主线：**原著知识提取与蒸馏**  
> G5｜正文诊断与修订最小闭环：**PAUSED**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是一键自动写整本书，也不是一个“蒸馏工具项目”。

长期目标是：

`参考作品知识 → 构思/规划 → 正文生成与修改 → 作者反馈 → 后台诊断/修订 → 状态维护`

最终使用形态应尽量接近真实作家工作：**作者负责方向、审美、重要创作选择和最终取舍；后台像一个长期稳定的编辑部与创作团队，负责学习参考作品、记住本书状态、按问题调用知识和专业能力、提出诊断/方案、执行机械维护。作者不需要管理 Agent、Skill、Prompt、Schema 或数据库。**

原著蒸馏只是这个工作台最前面的“学习能力”，不是项目终点。当前暂不扩展后面的写作闭环，是为了先把“参考作品如何真正变成可长期调用的创作知识”做好。

## 1.1 为什么还要自研 AI-write

自研的意义**不是重新制造 GitHub 上已经存在的能力**。

默认路线是：

`大量借用 / 复制 / 改造成熟项目`
`→ 少量自研连接层、知识协议和作者控制边界`
`→ 组成适合长期真实写作的一套工作台`

能被成熟项目完整满足的能力直接用，不为了“自主研发”重写。AI-write 只重点保留那些现有项目无法完整替代、又直接服务最终目标的部分：

- 参考作品知识与自己小说 Canon / Story State 严格隔离；
- 原著知识可追溯到 Evidence，并保留 scope / boundary / counterevidence / confidence；
- 不同上游的拆书、Reader、Craft、编辑诊断等结果最终收敛为统一、可检索的 BKP，而不是让 Writer 吞多套互不兼容报告；
- 知识必须按真实创作问题调用，最终服务构思、规划、写作与修订，而不是停留在拆书报告；
- 作者只面对小说本身，后台负责路由、检索、状态与机械执行；作者控制作品，但不承担系统审批和数据库管理。

判断任何新开发是否值得做，首先问：**它是否让未来真实写作更好或更省事？如果成熟上游已经解决，就优先直接吸收。**

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

这些证明了技术链能运行，但**还没有证明当前方法已经把原著中最值得学习的创作智慧提取得足够好**。当前重点是把已经选定的成熟上游观察能力真正接入执行层，而不是重新从零研究“小说里有什么值得提取”。

---

# 5. 当前实施重点

“怎样发现原著价值”的总体方案已经确定，当前不再把它当成开放架构问题反复讨论。下一步是**实施和验收已定方案**：

1. 直接吸收 / 复制 / 改造 oh-story 与 AI-Novel-Writing-Assistant 的长篇运行、逐章拆解、期待/兑现、情绪、信息推进、Evidence 回源、范围/预算/恢复等成熟能力；
2. 直接吸收 / 改造 creative-writing-skills 的 Reader / Page Craft / Writing Principles 观察方法，使其用于参考原著阅读，而不是只用于原创正文审阅；
3. 保留 Apodictic 作为高价值问题触发的 Developmental Deep Dive 工具箱；
4. 让上述观察能力直接消费 SourcePrepare 原著输入，并适配现有 Evidence / Observation / Inference / Boundary / BookProfile / BookDistill 链；
5. 不重写已经稳定的 SourcePrepare、BKP 协议和 KnowledgeRetrieve，除非实际融合暴露真实阻塞；
6. 融合完成后，用一部尚未蒸馏的新书跑完整链，验收“提取到了什么、漏了什么、哪些上游能力真正产生了增益”。案例用于暴露实现缺口，不重新决定总体架构。

当前允许多个流程、多个 Pass、多个 Skill。**不要求先做统一 orchestrator，也不要求作者只能一次操作。** 一键化属于后续产品体验优化，不反过来决定文学提取方法。

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

> **已经选定并融合的成熟原著观察能力，能在一部此前没有蒸馏的新书上直接读取原著、互补提取、必要深挖并经 BookDistill 收敛，最终形成高质量、可追溯、可检索的 BKP；同时能明确识别真实遗漏，而不是重新发明整套方法。**

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

> **AI-write 不从零重造 AI 写作系统：大量吸收成熟项目，少量自研连接层、知识协议和作者控制边界，把最好的现成能力组成一个真正服务长期写作的工作台；当前先完成其中最前面的“原著学习能力”。**