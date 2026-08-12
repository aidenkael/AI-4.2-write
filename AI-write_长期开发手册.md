# AI-write 长期开发手册

> 更新日期：2026-08-12  
> 当前正式 Gate：**G4｜创作上下文与作者决策最小闭环（ACTIVE / G4-B）**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史，避免手册持续膨胀。

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

作者控制的是：作品方向、审美、人物重大取舍和重要创作决定。

后台默认自动处理：知识检索、技能路由、上下文装配、连续性检查、从**已接受正文**提取明确事实、机械状态结算。

只有以下情况需要作者显式确认：

- 改变作品承诺、人物核心动机/关系走向、重要生死、世界基本规则、卷级方向等重大创作决定；
- 当前要求与既有 Author Intent / Canon 明显冲突；
- 文本事实有真实歧义；
- AI 准备引入正文中尚未成立的新解释、新剧情或新牺牲。

一句话：**作者负责创作判断，系统负责记住和执行；不要让作者成为数据库管理员。**

## 2.5 正式创作阶段性冻结工具

正式创作开始后，核心工作流默认阶段性冻结。除阻断性问题外，在卷末、故事弧结束或自然停顿点统一升级。

---

# 3. 原著知识与原创状态

## 3.1 BookDistill / BKP

原著是最高事实源。BookDistill 当前采用：

```text
长篇运行 / 读者动力：oh-story + AI-Novel
Reader / Page Craft：creative-writing-skills
必要 Developmental Deep Dive：Apodictic
→ BookDistill 总编辑回源核证、去重、组合效果、边界/反例/置信度
→ BKP
```

长期知识成熟度：

`Evidence → Observation / Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

单书最高默认 Work-specific Pattern；永久允许“重要但暂时无法命名”。

## 3.2 BKP 与 Canon 严格分离

- **BKP / Book Knowledge**：参考作品知识，只能提供启发、证据和比较。
- **Canon / Story State**：原创作品已成立事实和当前状态。

BKP 不能直接成为原创 Canon 的 authority source。

原创 Story State 的合法来源可以是：

- `author_decision`：作者明确确认的重大创作决定；
- `accepted_text`：作者已接受正文中清楚发生的事实；
- 必要的 `manual_import`。

AI 推演、候选方案、BKP Pattern、派生 Context 都不能直接成为 Canon。

---

# 4. 成熟作者能力地图

长期只用六区检查是否漏项，不扩成几十个固定技巧分类：

1. 作品方向与判断；
2. 故事运行能力；
3. 读者与文本效果；
4. 页面写作能力；
5. 判断与修订能力；
6. 长期知识与创作运行能力。

永久开放：**重要，但目前无法命名。**

C01–C20 只是技术路由，不是作者要操作的 20 个 Skill。

---

# 5. 核心长期上游

- **AI-Novel-Writing-Assistant**：完整长篇生产链、任务合同、Reader Experience Contract、拆书资产回流、状态回灌；不整体照搬自动导演哲学。
- **oh-story**：中文网文拆解、期待/回报、情绪/节奏、卷纲/细纲/正文回流。
- **creative-writing-skills**：Muse、Writer、Reader Sim、Character Sim、Critic、Editor、Outliner、Continuity；作者面对 Muse，后台路由专业能力。
- **Apodictic**：Developmental Editing 与“诊断而不夺权”的 Firewall。
- **InkOS**：author_intent、current_focus、Context Compiler、未来分支、状态治理、重动作确认。
- **graphify-novel / NovelForge**：Story Bible、source of truth 与派生层、结构化状态。
- **ani-book-skill**：人可读权威工件、渐进确认、确定性校验、已验收内容进入长期记忆。

出现真实问题时优先回到这些上游，不无限搜索。

---

# 6. 当前路线

- G0：CLOSED。
- G1：CLOSED。
- G2：CLOSED。
- G3：`G3_RETRIEVAL_VALIDATED / CLOSED`。
- **G4：ACTIVE / G4-B。**

G3 已证明跨书、小量、可追溯、有边界的 Retrieval；未证明 Cross-book Synthesis 和原创质量提升。

G4 解决两个问题：

1. **Cross-book Synthesis**：少量 BKP Hit 如何结合 Author Intent、Story State、当前任务和读者目标形成真正可用的方向；
2. **Author Decision Loop**：AI 提供方案/诊断/修改，作者保留重大取舍，后台可靠维护状态。

G4 只验证五种概念工件：

`Author Intent / Story State / Creation Brief / Context Package / Decision Record & State Diff`

子阶段：

`G4-A 最小合同 → G4-B 可丢弃沙盒状态 → G4-C Context Compiler + Synthesis → G4-D Author Decision Loop → G4-E 收口`

G4-A 已完成。G4-B 已建立一次性沙盒 `06_工作区/G4B_沙盒_雾港档案室/`，只读三份权威故事工件即可恢复作品方向、当前状态和当前任务；因此 G4-B 技术目标已满足候选，**尚未自动进入 G4-C**。

---

# 7. G4 状态写回原则

必须区分三类动作：

### A. 机械状态结算——默认自动

作者已接受正文后，文本中明确发生的事实、人物位置/资源变化、明确关系变化、已兑现线索等，可由系统自动提取并写回 Story State，保留 `accepted_text:<ref>` 来源。

### B. 创作性变更——作者决定

会改变重大方向、人物核心、世界规则、长期承诺的变更，AI 只能提议；作者明确确认后才以 `author_decision:<id>` 写回。

### C. 歧义/推断——暂停自动写回

如果事实并不明确，或状态更新包含正文没有直接成立的新解释，标记候选/冲突并询问作者，不得偷渡。

`approved_plan ≠ Canon`：未来计划即使被确认仍可推翻；真正发生的正文事实才属于已发生 Canon。

Context Package 是可重建派生层；依赖版本变化后即失效。旧 State Diff 不得覆盖新状态。

---

# 8. 当前禁止事项

- 不继续为了工程完整度打磨 Retrieval / 大型 RAG / KG；
- 不批量蒸馏几十本书；
- 不重跑《一九八四》《三体》；
- 不把单书 Pattern 写成普遍规则；
- 不从零重造成熟 Writer / Reader / Editor / Canon / Continuity；
- 不把正式长篇当未经验证工具的试验品；
- 不提前开发完整 UI / 独立客户端；
- 不让作者面对内部工具堆或频繁确认弹窗；
- 不让 AI 自动替作者做重大创作决定；
- 不把“作者控制”实现成“作者审批所有后台状态”；
- 未确认前不自动进入 G4-C。

---

# 9. Git 与文档纪律

长期禁止无明确授权执行：`reset / restore / clean / force push / rebase / merge`。

当前状态入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
跨阶段记忆：`00_项目控制/项目推进记忆.md`。

长期文档只保存稳定原则和当前边界；实验细节、过程报告放 `06_工作区` 或 Git 历史，避免每次发现都向手册追加新章节。

---

# 10. 一句话总纲

> **AI-write 要把优秀作品的创作智慧变成后台能力，让作者主要通过“看正文、说感觉、做重大取舍”来创作；AI 自动完成知识调用、专业技能路由、针对性修改、连续性维护和机械状态结算。**