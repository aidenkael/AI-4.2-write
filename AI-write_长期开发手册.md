# AI-write 长期开发手册

> 更新日期：2026-08-13  
> 当前正式 Gate：**G5｜正文诊断与修订最小闭环（ACTIVE / G5-B 待本地验证）**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是一键自动写整本书，也不是只会服从作者修改指令的文字工具。

作者主要面对：

`参考/研究 → 构思 → 规划 → 写 → 审阅 → 修改`

后台负责：

`Book Knowledge + Canon/Story State + Retrieval + Context Compiler + Planner + Writer + Reader/Critic/Editor + Continuity + State Writeback + Controller`

理想创作体验：

```text
工作台准备当前状态 + 少量相关知识
→ AI 生成/修改正文
→ 后台从文本本身做独立 Reader/Critic/Editor 诊断
→ 作者凭阅读感觉给自然语言反馈
→ Controller 区分作者目标、症状、原因判断和修法建议
→ 结合文本证据、专业诊断与 BKP，必要时同意、修正或挑战作者判断
→ 针对性修改正文
→ 作者继续阅读、接受、拒绝或再反馈
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

后台默认自动处理知识检索、技能路由、上下文装配、诊断、连续性检查、从已接受正文提取明确事实和机械状态结算。

只有重大创作变化、真实冲突/歧义，或正文尚未成立的新解释/新剧情需要作者显式确认。

## 2.5 作者反馈是信号，不是默认正确的诊断

作者对“我想要什么”“我接受什么”“哪些重大取舍我不愿意让步”拥有最终控制权；但作者对“为什么这段不好”“应该怎样修”不被系统默认视为客观真理。

系统应区分：

- **目标/约束**：作者真正想得到什么；
- **症状/感觉**：例如“这段太平”“这里拖”“这个人不像前面”；
- **原因判断**：作者或 AI 对问题原因的解释；
- **修法建议**：例如删半段、加冲突、换视角。

后两项默认是**待验证假设**。Controller 应结合正文证据、Reader/Critic/Editor、角色/连续性检查和相关 BKP 独立判断；有理由时应明确告诉作者“感觉成立，但你提出的原因或修法可能不对”，并给出更合适的替代方向。

AI 的诊断也不是绝对真理。多个诊断信号冲突时保留分歧、说明依据和不确定性，不用“AI 专业判断”夺走作者最终取舍。

## 2.6 正式创作阶段性冻结工具

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

长期只用六区检查漏项：作品方向与判断、故事运行、读者与文本效果、页面写作、判断与修订、长期知识与创作运行。

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

# 6. 已完成路线与当前 Gate

- G0：CLOSED；
- G1：CLOSED；
- G2：CLOSED；
- G3：`G3_RETRIEVAL_VALIDATED / CLOSED`；
- G4｜创作上下文与作者决策最小闭环：CLOSED；
- **G5｜正文诊断与修订最小闭环：ACTIVE。**

G4 已证明：可恢复创作状态、小 Context、按问题自然发生的跨书综合、作者自然语言 Decision/合法 Diff、revision/stale 边界。

G5 只验证下一条真实链：

`当前状态 + 新 Context → 一次性正文 → 独立 Reader/Critic/Editor 诊断 → 作者自然语言反馈 → Controller 三角校验 → 有依据的修订 → 作者判断`

G5-A 已固定“作者反馈不是默认诊断真理”的最小合同；G5-B 将用可丢弃沙盒生成一次正文并在**看不到作者反馈**的前提下先做独立诊断。

---

# 7. 当前禁止事项

- 不把作者每句话机械当成修改命令；
- 不把 AI/Reader/Critic 的判断包装成客观唯一答案；
- 不一次自研完整 Writer / Reader / Editor / Controller；
- 不拿正式长篇做尚未稳定工具的实验场；
- 不批量蒸馏更多书，只为填单个非阻塞 gap；
- 不升级 Retrieval/RAG/KG 只为结果更漂亮；
- 不开发完整 UI、大型数据库、KG 或多 Agent 平台；
- 不复用已因 state revision 变化而 STALE 的旧 Context；
- 不让 G5 自动扩大成“完整小说生产系统”。

---

# 8. Git 与文档纪律

长期禁止无明确授权执行：`reset / restore / clean / force push / rebase / merge`。

长期文档只保存稳定原则和当前边界；实验细节放 `06_工作区` 或 Git 历史。

本地历史 dirty / untracked / stash 先识别内容，再决定是否恢复或清理；不得自动 pop/drop/clean。普通同步不建立无意义长期分支。

当前状态入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
G5-A 合同：`06_工作区/G5A_作者反馈与诊断合同_v0.1.md`。  
G5-B Agent 任务：`06_工作区/G5B_Agent任务_一次性正文与独立诊断.md`。

---

# 9. 一句话总纲

> **作者拥有作品最终控制权，不等于作者对问题原因和修法永远正确；AI-write 要让后台专业能力既能听懂作者，也敢基于文本和证据提出不同判断，再把最终取舍交还作者。**