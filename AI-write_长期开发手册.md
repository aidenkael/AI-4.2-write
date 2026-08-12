# AI-write 长期开发手册

> 更新日期：2026-08-12  
> 当前正式 Gate：**G4｜创作上下文与作者决策最小闭环（ACTIVE / G4-C）**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是“一键自动写整本书”。

作者主要面对：

`参考/研究 → 构思 → 规划 → 写 → 审阅 → 修改`

后台负责：

`Book Knowledge + Canon/Story State + Retrieval + Context Compiler + Planner + Writer + Reader/Critic/Editor + Continuity + State Writeback + Controller`

理想创作体验：

```text
工作台准备当前状态 + 少量相关知识
→ AI 生成/修改正文
→ 作者凭阅读感觉给自然语言反馈
→ Controller/Muse 自动判断问题并调用相关技能
→ Writer / Character Sim / Reader Sim / Critic / Editor / Continuity 等针对性处理
→ 作者继续阅读、接受、拒绝或再给模糊反馈
→ 已接受正文中的明确事实自动结算进 Story State
→ 下一轮创作
```

作者不需要理解内部 Schema、手动挑 Skill、维护状态表或逐条审批机械记账。

---

# 2. 核心原则

## 2.1 Borrow-first

`真实问题 → 查成熟上游 → 最小真实测试 → 能借就借 → 只补剩余缺口`

AI-write 自研尽量集中在：**协议、路由、胶水、BKP、中文长篇适配、作者控制、必要状态接口。**

## 2.2 案例只暴露问题，不决定架构

单个章节、技巧或漏检不能直接升级成长期 Schema / Skill。回到完整能力地图和成熟上游，再判断是否存在系统性缺口。

## 2.3 真实任务优先

普通能力用少量真实任务判断；只有长期核心规则且证据矛盾、固化错误代价高时才升级严格 Benchmark。

## 2.4 作者控制 ≠ 作者审批

作者控制作品方向、审美、人物重大取舍和重要创作决定。

后台默认自动处理知识检索、技能路由、上下文装配、连续性检查、从已接受正文提取明确事实和机械状态结算。

只有重大创作变化、真实冲突/歧义，或正文尚未成立的新解释/新剧情需要作者显式确认。

## 2.5 正式创作阶段性冻结工具

正式创作开始后，核心工作流默认阶段性冻结；除阻断性问题外，在卷末、故事弧结束或自然停顿点统一升级。

---

# 3. 原著知识与原创状态

原著是最高事实源。BookDistill 当前采用：

```text
长篇运行 / 读者动力：oh-story + AI-Novel
Reader / Page Craft：creative-writing-skills
必要 Developmental Deep Dive：Apodictic
→ BookDistill 总编辑回源核证、去重、组合效果、边界/反例/置信度
→ BKP
```

知识成熟度：

`Evidence → Observation / Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

BKP 是参考作品知识；Canon / Story State 是原创作品权威事实。BKP、AI 推演和派生 Context 不能直接成为 Canon authority。

合法 Story State authority 可来自：`author_decision`、`accepted_text`、必要 `manual_import`。

---

# 4. 成熟作者能力地图

长期只用六区检查漏项：

1. 作品方向与判断；
2. 故事运行能力；
3. 读者与文本效果；
4. 页面写作能力；
5. 判断与修订能力；
6. 长期知识与创作运行能力。

永久开放：**重要，但目前无法命名。**

C01–C20 只是技术路由，不是作者操作的 20 个 Skill。

---

# 5. 核心长期上游

- AI-Novel-Writing-Assistant：完整长篇生产链、任务合同、Reader Experience Contract、拆书资产回流、状态回灌；
- oh-story：中文网文拆解、期待/回报、情绪/节奏、卷纲/细纲/正文回流；
- creative-writing-skills：Muse、Writer、Reader Sim、Character Sim、Critic、Editor、Outliner、Continuity；
- Apodictic：Developmental Editing 与“诊断而不夺权”的 Firewall；
- InkOS：author_intent、current_focus、Context Compiler、未来分支、状态治理、重动作确认；
- graphify-novel / NovelForge：Story Bible、source of truth 与派生层；
- ani-book-skill：人可读权威工件、渐进确认、确定性校验、已验收内容进入长期记忆。

出现真实问题时优先回到这些上游，不无限搜索。

---

# 6. 当前路线

- G0：CLOSED；
- G1：CLOSED；
- G2：CLOSED；
- G3：`G3_RETRIEVAL_VALIDATED / CLOSED`；
- **G4：ACTIVE / G4-C。**

G4-A 已完成最小合同。G4-B 已完成可丢弃原创沙盒与 cold-read 恢复验证。

当前 G4-C 验证：

`Author Intent + Story State + Creation Brief + 少量真实 BKP Hit → 小 Context Package → 情境化创作方向`

至少覆盖人物、情节/信息、读者体验三类问题。

G4-D 才验证作者选择/修改/拒绝与状态写回；当前不提前做。

---

# 7. G4-C 原则

- 必须真实运行现有 KnowledgeRetrieve；
- Retrieval 只负责召回，Synthesis 属于 Context Compiler / Muse / Planner；
- Context 只取当前任务需要的少量 Intent / State / BKP；
- 选择 BKP 时保留来源、Scope/Boundary/Confidence；
- 多书知识可以互补或冲突，不以“多数书这么写”制造规则；
- 只有一本书真正相关时不强行跨书；
- 无足够知识时明确 gap；
- Context 与候选方向都是派生物，不写 Canon；
- 无真实阻塞不升级 Retrieval / RAG / KG。

---

# 8. 当前禁止事项

- 不批量蒸馏更多书；
- 不重跑旧书；
- 不修改 BookDistill/BKP/KnowledgeRetrieve 只为让 G4-C 更漂亮；
- 不自研成熟 Writer / Reader / Editor / Canon / Continuity；
- 不拿正式长篇做工具实验；
- 不开发完整 UI；
- 不让作者面对内部工具堆或频繁确认；
- 不让 AI 自动替作者做重大创作决定；
- 不自动进入 G4-D。

---

# 9. Git 与文档纪律

长期禁止无明确授权执行：`reset / restore / clean / force push / rebase / merge`。

长期文档只保存稳定原则和当前边界；实验细节放 `06_工作区` 或 Git 历史。

当前状态入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
当前 G4-C Agent 任务：`06_工作区/G4C_Agent任务_最小Context与跨书综合.md`。

---

# 10. 一句话总纲

> **AI-write 要把优秀作品的创作智慧变成后台能力，让作者主要通过“看正文、说感觉、做重大取舍”来创作；当前 G4-C 正在验证参考智慧能否在真实创作现场被自动压成小而有用的 Context。**