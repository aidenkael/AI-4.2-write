# AI-write Agent 长期规则

> 目标：让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**当前唯一主线：原著知识提取与蒸馏。**

G0–G4 已关闭。G5｜正文诊断与修订最小闭环：**PAUSED**。不得继续要求作者评价 G5 测试正文。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项文件。

## 2. 当前方法链

`SourcePrepare → 初步作品识别/BookProfile → 多视角直接原著 Discovery → 按需 Deep Dive → BookDistill 总编辑收敛 → BKP → KnowledgeRetrieve`

当前固定的是职责链，不是 Skill 数量、Pass 数量或作者操作次数。

### SourcePrepare

只做作品身份、来源/版本、完整性、章节与标准输入。已有 PASS 可复用；REVIEW/FAIL 才停下报告。不得修改 `01_原始素材`。

### 初步 BookProfile

先建立结构、阶段、reader promise、显著/潜在强项与不确定项，用于导航后续阅读。Profile 可以随着后续原著阅读修订；不得把初步识别变成过滤器。

### Discovery

重要观察镜头必须直接读或回查原著，不只消费摘要。

默认两个互补方法源：

- `worldwonderer/oh-story-claudecode` + `AI-Novel-Writing-Assistant`：长篇运行、期待/兑现、情绪、信息释放、人物/关系、跨章回收；
- `haowjy/creative-writing-skills`：Reader / Page Craft、人物心智、POV、声音、句法、对话、动作、感官、留白和微观体验。

这两个只是默认镜头，不是固定“两次蒸馏”。作品需要更多视角可增加，明显无关可调整。Base Scan 的 MAP / Evidence / Observation / Boundary 属于阅读中的证据记录层。

### Deep Dive

只对真实高价值或高不确定问题触发。优先借 `anotherpanacea-eng/apodictic` 等成熟 Developmental Editing 镜头。次数不冻结。

### BookDistill

核心职责是总编辑式收敛：回原著核证、去重、识别跨尺度组合效果、区分 Observation / Inference、降级过度抽象、补 scope / boundary / counterevidence / confidence，再 Finalize BKP。

## 3. Borrow-first

当前优先直接借成熟上游，不继续泛搜：

- oh-story：拆文、逐章处理、聚合、章节边界与恢复；
- AI-Novel-Writing-Assistant：拆书工作台、范围定向、token 预算、增量/分档分析、证据回溯；
- creative-writing-skills：Reader / Craft；
- Apodictic：专项发展编辑；
- ani-book-skill：evidence-first、权威工件、确定性校验、恢复状态。

当前私人项目中许可证只做 provenance 记录，不作为技术路线阻塞。

“自研”指掌握架构、知识协议、数据边界、集成方式和验收标准，不要求每个具体能力由本项目重新实现。成熟能力优先复制、改造或组合后接入统一协议。

## 4. BKP 边界

BKP 长期保存作品身份、作品地图、BookProfile、Observation、重要 Inference、Work-specific Pattern、Deep Dive 最终知识，以及可追溯 Evidence / scope / boundary / counterevidence / confidence。

单书 BKP 不自动升级为普遍写作规则。正常写作阶段检索 BKP，不重新蒸馏原著。

## 5. 当前任务判断

当前优先解决原著提取质量，而不是先做一个统一 orchestrator 或单体 Skill。可以多流程、多 Pass、多 Skill；只有真实运行证明“操作碎片化本身阻碍提取质量/恢复”时，才优先做统一编排。

下一轮应使用一部尚未蒸馏的新书，真实检查初步识别、多视角提取、专项深挖和最终收敛各自的质量与遗漏。

## 6. 执行者 / 模型选择纪律

默认**不固定必须由 ChatGPT、Agent 或用户本人完成任务**。用户明确指定执行者时优先遵从；未指定时，直接按任务性质选择成功率高、操作简单、成本合理的执行方式，不把执行者选择重新丢给用户。

- ChatGPT 更适合：架构判断、方案设计、能力比较、Prompt / Skill / 协议 / Schema 设计、安全的小型 GitHub 修改、结果审查、知识压缩、跨来源综合、BKP Chief Editor，以及不依赖长时间本地运行的任务；
- Agent 更适合：本地多文件开发、长时间连续执行、大量逐章/逐文件处理、pytest / build / CLI / 日志调试、本地数据库和文件系统、批处理、checkpoint / resume，以及需要持续“执行 → 观察 → 修复 → 再执行”的任务；
- 混合任务可由 ChatGPT 锁定目标、协议、验收标准和最终审查，由 Agent 本地执行；但不是强制流程，单一执行者能更简单可靠完成时不要额外拆分；
- 用户主要负责：创作方向、审美和重要业务规则，UI 视觉验收，账号/权限/付款/API Key，高风险或不可逆操作确认，以及真正存在创作歧义时的选择。

模型选择仍按主任务：

- 代码、架构、脚本调试、Git/CI、本地运行占主导：可以推荐 Codex；
- 正文阅读、文本提取、总结归纳、章节分析、BKP 蒸馏、文学诊断占主导：不要优先推荐 Codex，选更适合中文长文本理解的模型；
- 混合任务按主任务选择一个模型，不做无必要细拆。

执行优先级：**操作简单与成功率 > 理论上的模型最优 > 过度细分工。** 不为了证明“自研”而自己实现已有成熟能力；不为了使用 Agent 而把简单任务复杂化；也不为了由 ChatGPT 完成而回避更适合 Agent 的本地长任务。

需要推荐时写清：执行者、模型、思考强度、备选/升级条件。

## 7. 当前禁止

- 不继续 G5 正文诊断/修订实验；
- 不要求作者阅读测试小说；
- 不把“一次操作 / 一个 Skill / 固定两遍”写成方法硬约束；
- 不固定所有作品相同 Discovery / Deep Dive 数量；
- 不批量蒸馏全部素材；
- 不升级 Retrieval/RAG/KG；
- 不开发 Writer/Reader/Editor/Controller/UI/大型数据库/多 Agent 平台；
- 不因为单本书一个特殊问题扩张长期架构。

## 8. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / `stash@{0}` 不清理、不覆盖、不自动 pop/drop。普通同步保持单一 `main`，不要为了临时保护留下无意义长期分支。

## 9. 当前验收标准

选一部此前未蒸馏的新书，跑完整“识别 → 多视角原著提取 → 必要深挖 → 总编辑收敛 → BKP”链。验收重点是知识质量、证据链、跨尺度发现、遗漏与最终可检索性，不要求一键化。

专项入口：`06_工作区/原著提取与蒸馏_当前目标.md`。