# AI-write 长期开发手册

> 更新日期：2026-08-13  
> 当前正式 Gate：**无；G4 已 CLOSED**  
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
→ Controller/Muse 自动判断问题并调用相关专业能力
→ 作者继续阅读、接受、拒绝或再给反馈
→ 已接受正文中的明确事实由后台机械结算 Story State
→ 下一轮创作
```

作者不需要理解内部 Schema、手动挑 Skill、维护状态表或逐条审批机械记账。

---

# 2. 核心原则

## 2.1 Borrow-first

`真实问题 → 查成熟上游 → 最小真实测试 → 能借就借 → 只补剩余缺口`

AI-write 自研尽量集中在：协议、路由、胶水、BKP、中文长篇适配、作者控制、必要状态接口。

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

原著是最高事实源。BookDistill 采用多视角直接读原著 + 总编辑收敛形成 BKP。

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

- AI-Novel-Writing-Assistant：完整长篇生产链、任务合同、Reader Experience Contract、状态回灌；
- oh-story：中文网文拆解、期待/回报、情绪/节奏、卷纲/细纲/正文回流；
- creative-writing-skills：Muse、Writer、Reader Sim、Character Sim、Critic、Editor、Outliner、Continuity；
- Apodictic：Developmental Editing 与“诊断而不夺权”的 Firewall；
- InkOS：author_intent、current_focus、Context Compiler、未来分支、状态治理、重动作确认；
- graphify-novel / NovelForge：Story Bible、source of truth 与派生层；
- ani-book-skill：人可读权威工件、渐进确认、确定性校验、已验收内容进入长期记忆。

出现真实问题时优先回到这些上游，不无限搜索。

---

# 6. 已完成路线

- G0：CLOSED；
- G1：CLOSED；
- G2：CLOSED；
- G3：`G3_RETRIEVAL_VALIDATED / CLOSED`；
- **G4｜创作上下文与作者决策最小闭环：CLOSED。**

G4 稳定结论：

- Author Intent / Story State / Creation Brief 可脱离聊天恢复；
- 小 Context 成立，跨书综合按问题自然发生；
- 非阻塞 BKP gap 不自动触发扩库；
- 作者自然语言反馈可以转成可追溯 Decision / 合法 Diff；
- `approved_plan ≠ Canon`，作者可推翻计划；
- state/intent revision 变化会使旧 Context 失效；
- `accepted_text → mechanical_settlement` 的 authority 与歧义边界已在协议层验证；
- 当前无 Retrieval / RAG / KG 升级理由。

G4 不证明 Writer 正文质量、生产级 accepted-text 抽取/写回、完整 Controller 或 UI 已完成。

---

# 7. 下一方向

当前没有 ACTIVE Gate。

从长期产品目标看，下一步自然方向是把已经证明的创作中枢接向真实正文执行：

`当前状态 + BKP + 创作任务 → 生成/修改正文 → 作者说感觉 → 后台路由专业能力 → accepted text 状态结算`

但仍坚持 Borrow-first；在新 Gate 正式建立前，不开始整个 Writer/Reader/Controller/UI 的大规模实现。

---

# 8. 当前禁止事项

- 不批量蒸馏更多书，只为填单个非阻塞 gap；
- 不修改 BookDistill/BKP/KnowledgeRetrieve 只为结果更漂亮；
- 不一次自研完整 Writer / Reader / Editor / Canon / Continuity；
- 不拿正式长篇做尚未稳定工具的实验场；
- 不开发完整 UI、大型数据库、KG 或多 Agent 平台；
- 不让作者面对内部工具堆或频繁确认；
- 不让 AI 自动替作者做重大创作决定；
- 不在没有新 Gate 的情况下继续堆功能。

---

# 9. Git 与文档纪律

长期禁止无明确授权执行：`reset / restore / clean / force push / rebase / merge`。

长期文档只保存稳定原则和当前边界；实验细节放 `06_工作区` 或 Git 历史。

本地历史 dirty / untracked / stash 先识别内容，再决定是否恢复或清理；不得自动 pop/drop/clean。普通同步不建立无意义长期分支。

当前状态入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
G4 收口：`00_项目控制/G4_启动记录_2026-08-12.md` 与 `06_工作区/G4B_沙盒_雾港档案室/g4e/G4E_CLOSEOUT.md`。

---

# 10. 一句话总纲

> **AI-write 要把优秀作品的创作智慧和复杂后台变成作者看不见的能力，让作者主要通过看内容、说感觉和做重大取舍来创作；G4 已证明最小创作中枢成立，下一 Gate 尚未建立。**