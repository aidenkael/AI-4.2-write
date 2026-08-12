# AI-write 长期开发手册

> 更新日期：2026-08-12  
> 文档定位：根目录长期开发总纲，供作者、ChatGPT 与 Agent 共同阅读。  
> 当前正式 Gate：**G4｜创作上下文与作者决策最小闭环（ACTIVE / G4-A）**。  
> 对应长期路线：**Phase E｜创作核心后台**。  
> G4 启动记录：`00_项目控制/G4_启动记录_2026-08-12.md`。  
> G4 启动前版本已原样归档：`99_归档/AI-write_长期开发手册_G4启动前_2026-08-12.md`。

---

# 0. 这份手册为什么存在

AI-write 的长期风险不是少一个功能，而是：

- 聊天里的重要判断没有写回项目，后续遗忘；
- 为赶阶段过早固化不成熟机制；
- 从零重造成熟上游已有能力；
- 把单书观察误写成普遍定律；
- 批量蒸馏后才发现知识粒度、观察方式或检索方式错了；
- 把作者变成系统操作员；
- 工程越来越严谨，但离“真正愿意继续看”的小说越来越远；
- 正式创作过程中频繁改工具，破坏沉浸和人物感觉。

因此，本手册负责长期目标、核心原则、知识资产、创作运行时、Borrow-first 上游、路线、禁止事项和阶段记忆。

## 文档优先级

1. **用户最新明确确认的意图最高。**
2. `00_项目控制/当前工作索引.md`：当前状态入口。
3. `00_项目控制/项目阶段门禁.md`：当前允许做什么、退出条件。
4. `00_项目控制/项目推进记忆.md`：跨阶段关键决策。
5. 本文件：长期架构与路线。

发生冲突时停止自动推进，先对齐再改。

---

# 1. 终极目标

AI-write 不是“自动替作者生成一本小说”，也不是“把 GitHub 小说项目全装进来”。

目标是建立一个真正能长期辅助不同题材、不同风格长篇小说创作的 AI 工作台：

```text
参考与研究
→ 作品构思
→ 故事规划
→ 场景 / 章节创作
→ 审阅与诊断
→ 修订
→ 状态回写
→ 下一轮创作
```

作者负责：

- 写什么；
- 人物和作品最终想表达什么；
- 哪个版本真正打动自己；
- 重大创作取舍；
- 灵感出现时推翻旧计划的权利。

后台负责：

```text
Book Knowledge
Canon / Story State
Retrieval
Context Compiler
Planner / Outliner
Writer
Character / Reader Simulation
Critic / Editor
Continuity
State Writeback
Controller / Router
```

## 1.1 核心闭环

```text
优秀作品
→ 学到真正值得保留的创作智慧
→ 固定成可追溯 BKP
→ 与原创 Canon / Story State 严格分离
→ 当前创作问题召回少量相关智慧
→ 与作者意图、人物、故事状态、读者目标共同进入 Context
→ Planner / Writer / Character Sim 重新创造
→ Reader / Critic / Editor / Continuity 检查效果
→ 作者最终判断
→ State Writeback
→ 下一轮创作
```

AI-write 不追求“所有单项都比别人强”，而是组合成熟上游，补真正缺口，形成适合真实作者长期使用的整体系统。

---

# 2. 核心开发哲学

## 2.1 Borrow-first

默认流程：

```text
真实问题
→ 查能力地图与核心上游
→ 完整理解成熟做法
→ 直接借 / 适配后借 / 只借方法 / 不适合
→ 最小真实测试
→ 吸收
→ 只有真实剩余缺口才自研
```

原则：

1. 不重复造轮子；
2. 不因项目整体很重而忽略成熟局部；
3. 不只摘容易工程化的片段而丢掉其完整工作逻辑；
4. 尽量通过薄接口组合成熟能力；
5. 不把 AI-write 自己想出的规则自动视为更优；
6. 当前私人研究阶段许可证不作为技术淘汰条件，但实际复制/修改必须保留来源、LICENSE、commit/tag、修改范围；未来公开/商用/服务化/分发前重新审计；
7. 工程稳定保证小说下限；人物生命力、读者体验、审美、张弛、欲望、幽默、悬念、留白、意外等决定上限。

AI-write 自研应尽量集中在：

> **协议、路由、胶水、BKP、中文长篇适配、作者控制、必要状态接口。**

## 2.2 案例只负责暴露问题，不负责决定架构

禁止：

`猫漏检 → 猫规则`  
`某个糕点漏检 → 糕点 taxonomy`

正确路径：

`案例暴露问题 → 成熟作者完整能力地图 → 查成熟上游 → 少量跨作品验证 → 只补系统性缺口`

## 2.3 真实任务优先，Benchmark 不是主项目

默认：strong baseline vs candidate → 少量真实任务 → 作者必要时快速判断 → 吸收/保留/放弃。

只有“长期核心规则 + 证据矛盾 + 固化错误代价高”时才升级严格 Benchmark。

B02 / B09 的方法学经验保留，但不复制成每个能力都要跑的大型研究工程。

## 2.4 作者不是机器

系统不能要求作者：

- 手动选择十几个 Skill；
- 天天维护几十份状态表；
- 记住所有伏笔；
- 严格服从旧大纲；
- 为系统一致性牺牲好创意。

作者偏离计划时：

`系统识别影响 → 说明后果 → 作者确认 → 更新计划 / Canon / Story State`

## 2.5 正式创作阶段性冻结工具

AI-write 可以持续成长，但进入正式创作后，核心 Skill / 工作流默认在一个创作周期内冻结。除阻断性故障外，优先在卷末、故事弧结束或自然停顿点统一升级。

---

# 3. 三方协作

## ChatGPT

适合：GitHub 调研、多项目比较、架构综合、路线判断、远端小型文档修改、设计 Agent 任务。

## Agent（本地）

适合：Windows / 文件系统 / 数据库真实运行、大量文件读取、代码实现、完整测试、本地 Benchmark、Git 状态核对。

## 作者

负责：创作效果、审美判断、重大产品取舍、Gate / 路线确认。

作者不承担代码、复杂 Schema 或技术架构判断。

---

# 4. “里子”和“面子”分离

优先建设里子：Book Knowledge、Canon/State、Retrieval、Context Compiler、Planning、Writer、Reader/Critic/Editor、Continuity、State Writeback、Controller。

作者界面近期可继续 Agent + Markdown/Git/Obsidian。是否做 Obsidian 插件、本地 Web 或独立客户端由真实使用痛点决定。

**后台必须与界面解耦。**

---

# 5. 作者层不面对十几个 Skill

作者只感知：

`参考/研究 → 构思 → 规划 → 写 → 审阅 → 修改 → 必要时项目级重规划`

后台可以有 Reader Sim、Character Sim、Canon、Retrieval、Writer、Critic、Editor、Controller 等，但 Skill、Agent、角色、脚本、知识库、数据库、服务不能混成同一个概念。

---

# 6. 成熟作者完整能力地图：六区

1. **作品方向与判断**：目标读者、作品承诺、类型、主题、审美目标、作品想成为什么；
2. **故事运行能力**：故事引擎、结构、人物、关系、世界、信息、悬念、兑现、长篇动力、卷/章/场景、因果与状态变化；
3. **读者与文本效果**：情绪、注意力、好奇、期待、欲望、幽默、恐惧、审美、沉浸、连续体验、微观→宏观效果链；
4. **页面写作能力**：语言、声音、POV、叙事距离、对白、潜台词、感官、动作、细节、意象、留白、句法与节奏；
5. **判断与修订能力**：Reader Sim、Critic、Editor、Developmental Editing、Scene Turn、Character Architecture、Emotional Craft、Reveal Economy、修订优先级；
6. **长期知识与创作运行能力**：学习参考作品、Book Knowledge、Canon/State、Retrieval、Context Compiler、作者意图、Continuity、State Writeback、Controller。

永久保留：**重要，但目前无法命名。**

C01–C20 继续作为技术路由，不是 20 个作者 Skill，也不是串行 Benchmark 排期。

---

# 7. 原著蒸馏与 BKP

## 7.1 原著蒸馏的真正目标

不是完成预设维度或制造整齐总结，而是：

> **尽可能发现并保存成熟作者真正会认为值得学习、值得记住、未来创作可能重新调用的作品智慧。**

允许宏观、中观、微观、人物因果、读者体验、跨章累积，以及“重要但暂时无法命名”的发现。

## 7.2 多视角 Discovery

```text
原著（最高事实源）
├─ 长篇运行 / 读者动力：oh-story + AI-Novel
├─ Reader / Page Craft：creative-writing-skills
├─ 必要 Developmental Deep Dive：Apodictic
└─ BookDistill 总编辑：回源核证 → 去重 → 组合效果 → Scope/Boundary/Counterevidence/Confidence → BKP
```

约束：

- 重要观察镜头直接读原著，不吃摘要链；
- BookProfile 是导航/预算工具，不是过滤器；
- 允许跨句、跨场景、跨章节组合证据；
- Discovery 可以宽，最终 BKP 必须克制；
- 不围绕单个案例硬编码；
- 方法升级不要求重跑《一九八四》《三体》。

## 7.3 BKP 认识论边界

BKP 是参考作品长期知识资产，不是写作规则表。

`Source Evidence → Observation / Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

- 单书最高默认只到 Work-specific Pattern；
- 跨书重复只增加支持度；
- Production Rule 极少；
- 无法可靠抽象但重要的东西可以长期停留 Observation / Inference；
- Scope / Boundary / Counterevidence / Confidence 尽量保留。

参考书知识与原创 Canon 必须严格分离。

---

# 8. G3 正式结论

2026-08-12：**G3｜跨书知识库与创作任务检索 `G3_RETRIEVAL_VALIDATED / CLOSED`。**

已证明：

- 《一九八四》《三体》两个正式 BKP 可进入统一入口；
- 真实创作问题可跨书召回少量相关知识；
- 返回结果数量受控、可追溯、保留 Scope/Boundary/Counterevidence/Confidence；
- 单书 Pattern 不因检索自动升级；
- 当前最小 KnowledgeRetrieve 足以证明链路，`NO_RAG_UPGRADE`。

未证明：

- BKP 捕获全部作品精华；
- Cross-book Synthesis；
- Writer 原创质量提升；
- 当前关键词/bigram 是最终检索架构；
- 出现 Production Rule。

G3 closeout 前已完成成熟作者六区审查和多视角 Discovery 方法修正。

完整记录：`00_项目控制/G3_收口记录_2026-08-12.md`。

---

# 9. G4｜创作上下文与作者决策最小闭环

## 9.1 当前状态

**ACTIVE / G4-A。**  
建立日期：2026-08-12。  
对应 Phase E｜创作核心后台。  
正式边界：`00_项目控制/G4_启动记录_2026-08-12.md` 与 `项目阶段门禁.md`。

## 9.2 为什么先做 G4

G3 之后两个正式系统性问题是：

1. **Cross-book Synthesis**：召回的参考智慧怎样结合当前原创作品情境，形成真正可用的方向；
2. **Author Decision Loop**：AI 怎样提供方案、证据、风险、推演，而作者仍掌握重大决定，并在确认后可靠写回状态。

它们共同依赖最小 Author Intent、Story State、Creation Brief、Context Compiler、Decision / State Diff，所以 Phase E 第一个 Gate 先做“神经中枢”，不先做 Writer。

## 9.3 G4 唯一核心目标

证明系统可以把：

```text
作者意图
+ 当前 Canon / Story State
+ Current Focus
+ 希望读者经历什么
+ 少量相关 BKP Hit
```

编译成小而相关、来源清楚的 Context Package，再给作者 1～3 个真正有差异的方向；每个方向说明依据、风险、冲突、边界；作者可选择、修改、全部拒绝；**作者确认前不写 Canon，确认后才生成 State Diff / Decision Record 并写回。**

G4 不证明正文质量。

## 9.4 五种概念工件

### Author Intent
作品想成为什么；作者当前最在意什么；明确不想要什么；Current Focus。

### Story State / Canon
原创作品权威事实与当前状态：世界、人物、关系、已发生事件、悬念/伏笔/承诺、已确认计划。

### Creation Brief
当前创作问题、人物欲望/阻力、读者目标、必须继承的事实/承诺、硬约束、自由探索空间。

### Context Package
由 Author Intent + relevant State/Outline + Creation Brief + 少量 BKP Hit 派生。必须有来源、选择理由、规模控制、可重建性；不是权威事实。

### Decision Record / State Diff
记录方案、风险、代价、参考知识、作者选择/修改/拒绝，以及确认后的明确状态变化。

## 9.5 Borrow-first 分工

- **InkOS**：主骨架——Author Intent、Current Focus、Context Compiler、未来分支、确认后状态治理；
- **AI-Novel-Writing-Assistant**：任务合同、书/卷/章/场景层次、Reader Experience Contract；
- **graphify-novel + NovelForge**：Story Bible / Canon、source of truth 与派生层、结构化状态；
- **ani-book-skill**：人可读权威工件、确定性校验、作者确认后进入长期事实；
- **creative-writing-skills**：Muse、多方案探索、后台专业角色隐藏路由；
- **Apodictic**：决策诊断 Firewall；
- **oh-story**：中文长篇期待/回报、压力/换气、章节推进与追读动力。

## 9.6 子阶段

```text
G4-A 最小合同
→ G4-B 可丢弃原创沙盒状态
→ G4-C Context Compiler + Cross-book Synthesis 最小原型
→ G4-D Author Decision Loop 验证
→ G4-E 收口判断
```

当前只推进 **G4-A**。

## 9.7 G4-A 当前任务

定义五种概念工件的：

- 最小字段；
- 权威 vs 派生边界；
- 谁可建议、谁可写入；
- 什么必须作者确认；
- 最小 provenance / trace；
- 哪些上游字段不搬；
- G4-B 实现前必须稳定的接口。

不在 G4-A 提前实现沙盒、Context Compiler 代码、Synthesis、Writer 或完整评审链。

## 9.8 G4 closeout 最低证明

必须至少证明：

- 权威状态文件化，不依赖聊天；
- BKP 与 Canon 严格分离；
- Context Package 小而相关、来源清楚、可重建；
- 偏人物 / 偏情节信息 / 偏读者体验等不同问题都能情境化综合；
- 1～3 个方向真正有差异并说明边界、风险、依据；
- 作者可选择/修改/拒绝；
- 确认前不写 Canon，确认后有 State Diff / Decision Record；
- 新会话只读权威工件即可恢复状态和最近重大决定；
- 不因 G4 升级 Retrieval/RAG/KG；
- 作者明确验收后才能退出。

完整 14 项条件见 G4 启动记录。

---

# 10. 核心长期上游参照

## AI-Novel-Writing-Assistant

参照完整 AI Native 小说工作台、拆书资产回流、Reader Experience Contract、书/卷/章/场景生产链、审核/修复、状态回灌和长任务恢复。**不整体照搬自动导演产品哲学。**

## oh-story

参照中文网文拆解、剧情单元、情绪/节奏、期待/回报、拆解资产进入卷纲/细纲/正文、长篇追踪、去 AI 味。

## creative-writing-skills

参照 Muse、Writer、Critic、Editor、Reader Sim、Character Sim、Outliner、Continuity、Writing Principles、Page Craft。

## Apodictic

参照 Developmental Editing、Reader Experience、Character Architecture、Reveal Economy、Scene Turn、Emotional Craft、Decision Pressure、POV/Voice，以及“诊断而不夺权”的 Firewall。

## InkOS

参照 author_intent、current_focus、Context Compiler、未来分支、Canon/State、写作→审计→修订→状态回灌与作者确认治理。

## NovelForge / graphify-novel / ani-book-skill

分别参照结构化资产与工作流、Story Bible / source-of-truth 与派生图谱、人可读权威文件与确定性校验。

次级候选继续按真实问题触发，不无限搜索。

---

# 11. 当前长期路线

- Phase A｜能力层成熟上游复查：阶段性目标完成；
- Phase B｜BKP + BookProfile vNext：阶段性目标完成；
- Phase C｜BookDistill vNext：技术验证完成；
- Phase D｜跨书知识库与检索：**G3 CLOSED**；
- Phase E｜创作核心后台：**进行中，当前 G4**；
- Phase F｜创作沙盒：G4 之后，用可丢弃真实创作跑完整链，不拿正式长篇当试验品；
- Phase G｜冻结 Production v1.0；
- Phase H｜正式长篇 + 面子演进。

Phase E 不等于一个巨大 Gate。应按真实依赖拆成小 Gate；当前 G4 只做上下文与作者决策神经中枢。

---

# 12. G4 当前禁止事项

1. 不直接实现完整 Writer；
2. 不直接实现完整 Reader Sim / Critic / Editor；
3. 不跑正式长篇，不拿 `03_作品工程` 当工具试验品；
4. 不开发 UI / Obsidian 插件 / 独立客户端；
5. 不建立大型数据库、Knowledge Graph、向量库；
6. 不升级 KnowledgeRetrieve，只为更先进；
7. 不建立大型多 Agent 平台；
8. 不把上游 schema 合成超级 schema；
9. 不因一个沙盒冻结最终 Canon schema；
10. 不让 BKP 自动写入 Canon；
11. 不让 AI 在作者确认前修改重大 Story State；
12. 不让 Controller 自动替作者选重大方向；
13. 不整体照搬 AI-Novel 自动导演哲学；
14. 不顺手做后续 Gate；
15. 不重启 B02/B09；
16. 不批量蒸馏参考书；
17. 不重跑《一九八四》《三体》；
18. 不为了 G4 改 BookDistill/BKP/Retrieval，除非真实阻塞；
19. 不把 Cross-book Synthesis 塞回 Retrieval 变成“超级大脑”；
20. 不未经作者确认自动退出 G4。

---

# 13. Git 与资产安全

- 不自动清理不明来源 dirty / untracked；
- 不覆盖 Local Only；
- 不执行 `reset / restore / clean / force push / rebase / merge`，除非用户明确授权并确认风险；
- 远端小型文档修改可由 ChatGPT 直接完成；
- 涉及本地大量文件、真实数据库、运行测试时优先交 Agent。

2026-08-12 `BookDistill/SKILL.md` 的重复同名 commit 已定性为历史噪音：最终内容正确，不清理 main 历史，不建立未来清理任务。

---

# 14. 阶段结束闭环

每个 Gate closeout 必须同步：

1. 本手册；
2. `当前工作索引.md`；
3. `项目推进记忆.md`；
4. `项目阶段门禁.md`；
5. `AGENTS.md`（阶段状态或长期规则写在其中时）；
6. 相关 STATUS / provenance / 启动或 closeout 记录。

然后 commit、报告 SHA，明确“已证明 / 未证明”，并把下一阶段问题明确归属。**没有用户确认，不自动退出当前 Gate。**

---

# 15. 当前状态快照

<!-- AUTO:CURRENT_STATE START -->
- G0：CLOSED。
- G1：CLOSED。
- G2：CLOSED。
- G3：`G3_RETRIEVAL_VALIDATED / CLOSED`。
- G4｜创作上下文与作者决策最小闭环：**ACTIVE**。
- 当前子阶段：**G4-A｜成熟上游压缩成最小合同**。
- G4 只验证 Author Intent、Story State/Canon、Creation Brief、Context Package、Decision Record/State Diff 五种概念工件及其闭环。
- Cross-book Synthesis 与 Author Decision Loop 是 G4 的正式问题；正文质量不属于 G4。
- 当前不实现 Writer、完整 Reader/Critic/Editor、正式长篇、UI、大型 RAG/KG/数据库/多 Agent 平台。
<!-- AUTO:CURRENT_STATE END -->

<!-- AUTO:NEXT_ACTIONS START -->
## 下一步

1. 完成 G4-A 最小合同：五种概念工件的最小字段、权威/派生边界、写入权限、作者确认点、provenance/trace。
2. 对核心上游只做与这些合同直接相关的有边界复核；不扩大搜索。
3. G4-A 产物稳定后，再决定 G4-B 的一次性原创沙盒实现方式。
<!-- AUTO:NEXT_ACTIONS END -->

<!-- AUTO:OPEN_RISKS START -->
## 当前开放风险

- Canon schema 过早膨胀；
- Context Package 仍可能把太多信息塞给模型；
- Cross-book Synthesis 可能把参考经验误写成规则；
- 多方案输出可能退化为三个同义改写；
- 作者确认门不清晰可能造成状态污染；
- AI 建议与权威事实边界不清可能污染 Canon；
- 多模块架构可能再次把作者变成系统操作员；
- Discovery 仍需未来新书验证；
- 超长网文 / 低质量作品 / 全能型作品仍是未来触发式回归条件。
<!-- AUTO:OPEN_RISKS END -->

---

# 16. 一句话总纲

> **从优秀作品中学习真正有价值的创作智慧，在当前原创作品的作者意图和故事状态下重新创造，用读者体验检验效果，并持续写回长篇状态；G4 先把“作者想要什么、作品现在是什么、当前问题是什么、参考智慧怎么进入、确认后状态怎么变”这条神经中枢做稳。**