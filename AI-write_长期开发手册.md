# AI-write 长期开发手册

> 更新日期：2026-08-13  
> 当前主线：**单书蒸馏成品化**  
> G5｜正文诊断与修订最小闭环：**PAUSED**  
> 本文件只保留长期有效原则、当前路线和关键边界；过程细节放专项文件与 Git 历史。

---

# 1. 项目目标

AI-write 是**作者主导、AI 辅助**的中文长篇小说创作工作台，不是一键自动写整本书。

长期目标仍是：

`参考作品知识 → 构思/规划 → 正文生成与修改 → 作者反馈 → 后台诊断/修订 → 状态维护`

但当前不继续扩展写作闭环。先把最前面的“参考作品知识”做成真正可用的成品。

---

# 2. 当前唯一主线：一本书如何完成蒸馏

用户侧体验必须尽量简单：

`指定书名/book_id → 一次启动 → 等待 → BookProfile + 可检索 BKP + 简短完成报告`

内部复杂度由 Agent 承担，作者不负责执行命令、选择 Deep Dive、维护 Evidence 或理解 BKP Schema。

## 2.1 SourcePrepare

SourcePrepare 负责输入标准化，不算文学蒸馏。

它把 `01_原始素材` 中的 EPUB/TXT/PDF 只读转换与质检为 PASS 的：

`full.md + chapters/ + metadata.json + conversion_report.md`

只有 PASS 才进入 BookDistill；REVIEW/FAIL 才需要人工介入。

## 2.2 BookDistill 内部分析

生产口径统一为：

> **2 次全书蒸馏 + 默认 0–2 次按需专项深挖 + 1 次总编辑式收敛。**

1. **Discovery Pass A｜长篇运行 / 读者动力**：直接读全书原文，重点观察故事发动机、作品承诺、章节/场景功能、期待/兑现、情绪生态、信息释放、人物/关系推进、跨章回收和追读动力。MAP、FACT、INFERENCE、OBSERVATION、BOUNDARY 等 Base Scan 基础记录在这一 Pass 与 Pass B 的阅读过程中一并产生，**Base Scan 是证据记录层，不再算第三次全书文学蒸馏。**
2. **Discovery Pass B｜Reader / Page Craft**：再次直接读全书原文，重点观察逐时阅读体验、人物心智可信度、POV/叙事距离、声音、句法与节奏、对话/潜台词、动作/感官/留白、微观机巧和跨尺度组合效果。
3. **BookProfile**：汇总覆盖、强项、潜在强项、不确定项，并决定是否需要专项预算；它是导航，不是额外一次蒸馏。
4. **Deep Dive｜默认 0–2 个专项**：只对高价值或高不确定问题触发，读取相关章节/主题，不重新无差别扫描整书；一本书确有明显额外价值时可以超过 2 个，但最终报告必须说明原因。
5. **总编辑式 Finalize**：回原著核证、合并重复、识别跨尺度效果链、补 scope/boundary/counterevidence/confidence，形成正式 BKP；这是综合与核证，不算第三次全书蒸馏。

“Pass”是分析目标，不等于一次模型调用。长书可以按章节/稳定分块执行，同一 Pass 的中间结果落盘，再做跨章收敛。

《一九八四》《三体》验证时各做了 3 次专项 Deep Dive，只证明 v0.2 流程能运行；**不把 3 次冻结为以后每本书的固定规则。**

---

# 3. 蒸馏最终得到什么

BKP（Book Knowledge Package）是一部参考作品完成蒸馏后的长期知识资产。

作者默认只需要看到：

1. **BookProfile**：这本书在哪些创作问题上值得参考、主要强项、潜在强项、不确定项、已完成专项；
2. **可检索 BKP**：未来真正写作时由后台按问题调用；
3. **简短完成报告**：来源、覆盖、Deep Dive、校验和 Retrieval 可发现状态。

BKP 内部长期保存：

- 作品身份与 source fingerprint；
- 作品地图；
- Observation；
- 重要 Inference；
- Work-specific Pattern；
- Deep Dive 最终知识；
- 对应 Evidence、scope、boundary、counterevidence、confidence。

逐章 evidence、manifest、Agent 工作记录和测试日志主要是后台审计材料，不是作者日常阅读材料。

正常写作阶段只检索 BKP，不重新蒸馏原著。

---

# 4. 当前已有能力

- SourcePrepare v0.2.1：稳定地基；
- BookDistill v0.2：证据记录、多视角 Discovery、BookProfile、Deep Dive、BKP Finalize 已存在；
- 《一九八四》《三体》已完成真实 vNext 验证；
- KnowledgeRetrieve 已能加载正式 BKP。

因此当前缺口不是继续设计新的蒸馏理论，而是**把现有零件收成一个单书编排入口**。

---

# 5. 当前开发任务

优先复用现有 SourcePrepare / BookDistill，实现：

`书名/book_id`
`→ 判断 SourcePrepare 是否已有 PASS；必要时运行`
`→ Discovery A`
`→ Discovery B`
`→ BookProfile 自动决定默认 0–2 个 Deep Dive`
`→ 总编辑式收敛`
`→ BKP Finalize`
`→ 校验 KnowledgeRetrieve 可发现`
`→ 一份简短最终报告`

需要补的主要是：

- 单书 orchestrator / runbook；
- 阶段状态判断；
- 自动选择/记录 Deep Dive；
- 失败时明确停在哪一步、为什么；
- 中断后的最小恢复能力；
- 一次真实新书端到端验收。

不重写已经稳定的 SourcePrepare / BookDistill 确定性核心，除非真实端到端运行暴露阻塞。

---

# 6. 长期核心原则

## 6.1 Borrow-first

`真实问题 → 查成熟上游 → 能借就借 → 最小适配 → 真实运行`

成熟实现能直接复用时，不重复造轮子。当前私人项目中，许可证只做 provenance 记录，不作为技术路线阻塞。

## 6.2 案例只暴露问题，不决定架构

单本书的特殊问题不能直接升级成永久 Schema / Skill。

## 6.3 原著是最高事实源

重要观察必须能回到原著证据；BookProfile、BKP、Agent 推断都不能替代原著。

## 6.4 发现可以宽，最终 BKP 必须克制

允许多视角、跨尺度、未命名发现；最终只保留长期有调用价值、证据充分、边界清楚的知识。

## 6.5 单书不能证明普遍规律

单本 BKP 最高默认只到：

`Evidence → Observation / Inference → Work-specific Pattern`

Cross-book Pattern、Creation-tested Heuristic、Production Rule 属于后续阶段。

## 6.6 作者控制 ≠ 作者审批

后台机械工作默认自动完成。只有来源 REVIEW/FAIL、作品身份冲突或真正无法裁决的重大问题才打断作者。

---

# 7. 暂停的后续工作

G5 正文诊断与修订实验暂停。已有 G5 工件保留为历史证据，不删除，也不继续要求作者阅读测试正文。

在单书蒸馏入口完成前，不继续：

- Writer / Reader / Critic / Editor / Controller 实质开发；
- 正文质量 Benchmark；
- UI；
- 大型数据库、RAG、KG、多 Agent 平台；
- 批量蒸馏全部素材。

---

# 8. 当前完成标准

当前主线完成只需要证明：

> **选一部此前没有蒸馏的新书，用户只指定一次书名/book_id；Agent 可以从 SourcePrepare 状态判断开始，自动完成两次全书 Discovery、必要专项深挖、最终 BKP，并让 KnowledgeRetrieve 成功发现。**

如果成功，这一版才可以称为“单书蒸馏成品”。

---

# 9. Git 与文档纪律

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

本地 dirty / untracked / stash 先识别内容再处理，不自动 pop/drop/clean，不为了普通同步建立无意义长期分支。

长期文档只留稳定原则和当前路线；具体实现过程放 `06_工作区` 和 Git 历史。

当前入口：`00_项目控制/当前工作索引.md`。  
当前门禁：`00_项目控制/项目阶段门禁.md`。  
专项目标：`06_工作区/单书蒸馏成品化_当前目标.md`。

---

# 10. 一句话总纲

> **当前先不研究 AI 怎么把小说写好；先把“一本参考书一次交给 Agent → 两次互补全书蒸馏 → 必要专项深挖 → 一个高质量、可追溯、可检索 BKP”做成真正可用的成品。**