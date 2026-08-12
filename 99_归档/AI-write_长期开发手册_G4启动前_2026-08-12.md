# AI-write 长期开发手册

> 更新日期：2026-08-12  
> 文档定位：AI-write 根目录长期开发总纲，供作者、ChatGPT 与 Agent 共同阅读。  
> 当前正式状态：**G3｜跨书知识库与创作任务检索已完成，`G3_RETRIEVAL_VALIDATED / CLOSED`。当前未自动建立下一 Gate。**  
> 下一长期方向：**Phase E｜创作核心后台**；启动前必须由作者确认新的 Gate 名称、唯一目标、最小退出条件和禁止范围。  
> G3 收口前旧版详细手册已原样归档：`99_归档/AI-write_长期开发手册_G3收口前_2026-08-12.md`。  
> G3 详细收口理由：`00_项目控制/G3_收口记录_2026-08-12.md`。

---

# 0. 这份手册为什么存在

AI-write 的长期风险不是“少一个功能”，而是：

- 聊天里形成的重要判断没有写回项目，后续遗忘；
- 为了赶阶段而过早固化不成熟机制；
- 自己从零研发成熟上游已经解决的能力；
- 把单本小说的观察误写成普遍写作定律；
- 蒸馏大量作品后才发现知识粒度、观察方法或检索方式不对；
- 把作者变成系统操作员，让作者面对几十个 Skill、报告和配置；
- 工程越来越严谨，但离“真正写出愿意继续看的小说”越来越远；
- 正式创作过程中频繁改工具，破坏作者的沉浸、人物感觉和创作连续性。

因此，本手册长期负责：

1. 项目最终目标；
2. 核心开发原则；
3. 原著知识资产的认识论边界；
4. 创作运行时的长期架构；
5. Borrow-first 的上游参照池；
6. 当前路线与阶段边界；
7. 禁止事项；
8. 阶段收口时必须同步的记忆规则。

## 文档优先级

- **用户最新明确确认的意图永远最高。**
- `00_项目控制/当前工作索引.md` 是当前状态入口。
- `00_项目控制/项目阶段门禁.md` 决定当前允许做什么、何时才能进入下一 Gate。
- `00_项目控制/项目推进记忆.md` 保存跨阶段必须记住的重大决策。
- 本文件负责长期架构与路线，不替代当前门禁。
- 如出现冲突：停止自动推进，比较差异，再由作者确认后同步修正。

---

# 1. 终极目标

AI-write 不是“自动替作者生成一本小说”，也不是“把所有 GitHub 小说项目安装进一个仓库”。

目标是建立一个真正能长期辅助不同题材、不同风格长篇小说创作的 AI 工作台：

```text
参考与研究
    ↓
作品构思
    ↓
故事规划
    ↓
场景 / 章节创作
    ↓
审阅与诊断
    ↓
修订
    ↓
状态回写
    ↓
下一轮创作
```

后台持续存在：

```text
Book Knowledge（参考书知识）
Canon / Memory（原创作品事实与状态）
Retrieval（检索）
Context Compiler（上下文装配）
Planner / Outliner
Writer
Character / Reader Simulation
Critic / Editor
Continuity
State Writeback
Controller / Router
```

作者真正需要做的是：

- 决定写什么；
- 决定人物和作品最终想表达什么；
- 判断哪个版本更打动自己；
- 做重大创作取舍；
- 在灵感出现时允许推翻旧计划。

AI 工作台负责：

- 管素材和参考书；
- 把参考书一次性知识化；
- 维护人物、关系、世界、伏笔、时间线和当前状态；
- 从知识库自动找相关经验；
- 给出规划与可选创作方向；
- 辅助正文；
- 做连续性、人物、节奏、对白、情绪、信息、读者体验等诊断；
- 根据作者确认修订；
- 把真正发生的内容写回状态。

## 1.1 项目存在价值与核心闭环

AI-write 不以“功能数量全面超过所有 GitHub 小说项目”为目标。

真正值得建立的闭环是：

```text
优秀作品
→ 系统学习其中真正值得保留的创作智慧
→ 形成长期可调用的原著知识资产
→ 与原创作品 Canon / Story State 严格分离
→ 在真实创作问题出现时召回少量相关智慧
→ 与作者意图、人物、故事状态和读者目标共同进入创作
→ Planner / Writer / Character Sim 等重新创造
→ Reader / Critic / Editor / Continuity 检查真实效果
→ 作者最终判断
→ 写回 Story State
→ 下一轮创作
```

如果成熟上游已经完整可靠地解决某一环，停止重复自研，改为直接借用、适配或组合。

> **AI-write 的目标是组合成熟上游能力，补足现有项目没有解决好的关键缺口，形成最适合真实作者长期创作的整体工作台。**

---

# 2. 核心开发哲学

## 2.1 Borrow-first：先借成熟智慧，再写自己的胶水

默认顺序：

```text
真实问题
→ 查能力地图和成熟上游
→ 阅读其完整方法与实现
→ 判断：直接借 / 改造后借 / 只借方法 / 不适合
→ 最小真实测试
→ 吸收有用部分
→ 只有真实缺口仍存在时才自研
```

原则：

1. **Borrow-first，不重复造轮子。**
2. 不因为一个项目整体很重，就忽略其中可以拆走的成熟能力。
3. 不只摘项目中最容易工程化的局部，而无意丢掉它真正有价值的完整工作逻辑。
4. 尽量通过薄接口组合成熟能力。
5. 不把“AI-write 自己想出来的规则”自动视为更好。
6. 当前私人/非商业研究阶段，许可证类型不作为技术候选淘汰标准；实际复制仍保留来源、LICENSE、commit/tag 和修改范围，未来公开/商用/服务化/分发前重新审计。
7. 工程稳定负责小说下限；人物生命力、读者体验、审美、张弛、欲望、幽默、悬念、留白、意外等决定小说上限，两者都必须进入整体工作台。

## 2.2 案例只负责暴露问题，不负责决定架构

禁止：

`猫漏检 → 新增猫规则`  
`桂花糕漏检 → 新增糕点规则`

正确流程：

```text
具体案例暴露问题
→ 放回成熟作者完整能力地图
→ 判断属于哪类能力
→ 检查成熟上游
→ 少量真实作品验证
→ 只补真正剩余的系统性缺口
```

架构由：

**完整能力需求 + 成熟上游 + 跨作品验证**

共同决定。

## 2.3 真实任务优先，Benchmark 不是主项目

能通过真实任务快速判断的问题，不升级成研究型 Benchmark。

默认只做：

```text
strong baseline
vs candidate
→ 少量真实任务
→ 必要时作者快速判断
→ 吸收 / 保留候选 / 放弃
```

只有同时满足以下条件，才升级严格 Benchmark：

- 机制会成为长期核心规则；
- 证据互相矛盾；
- 固化错误的代价很高。

B02 / B09 的方法学经验保留，但不再复制成每个能力都要跑的大工程。

## 2.4 作者不是机器

工作台不能要求作者：

- 手动选择十几个 Skill；
- 天天审核几十份内部报告；
- 记住所有伏笔和状态；
- 严格服从旧大纲；
- 为系统一致性牺牲突然出现的好创意。

作者偏离计划时：

```text
系统识别影响
→ 告诉作者会改变什么
→ 作者确认
→ 更新计划 / Canon / Story State
```

系统服务作者，而不是作者服务系统。

## 2.5 开发顺序必须符合真实作者的工作方式

准备阶段可以检查、改进、组合创作工具。

进入正式创作以后：**默认阶段性冻结核心 Skill / 工作流。**

优先在：

- 一个场景组结束；
- 一个小故事弧结束；
- 卷末；
- 阶段末；
- 自然停顿点；

统一复盘升级。

除阻断性故障外，不让作者写到一半长期处于“软件测试员模式”。

## 2.6 系统持续成长，但正式创作阶段性冻结

两者不矛盾：

```text
系统长期：真实创作 → 暴露不足 → 查成熟上游 → 最小验证 → 升级

单个正式创作周期：冻结核心工作流 → 连续创作 → 阶段末统一复盘
```

---

# 3. 三方协作分工

## ChatGPT

适合：

- GitHub 调研；
- 多项目比较；
- 架构综合；
- 路线判断；
- 远端少量安全文档修改；
- 给 Agent 设计明确任务。

## Agent（本地）

适合：

- 本地大量文件读取；
- Windows / 文件系统 / 数据库真实运行；
- 代码实现；
- 完整测试；
- 本地 Benchmark；
- Git 提交与运行环境验证。

## 作者

负责：

- 创作效果；
- 审美判断；
- 重大产品取舍；
- Gate / 路线确认。

作者不承担代码、Schema、复杂技术架构判断。

---

# 4. “里子”和“面子”必须分离

## 4.1 里子：真正决定能力的后台

优先建设：

- Book Knowledge；
- Canon / Memory；
- Retrieval；
- Context Compiler；
- Planning；
- Writer；
- Character / Reader Simulation；
- Critic / Editor；
- Continuity；
- State Writeback；
- Controller / Router。

## 4.2 面子：作者从哪里使用

近期不急于做独立软件。

推荐演进：

```text
当前开发：Agent + Markdown/Git
        ↓
近期作者工作：Agent + Obsidian
        ↓
中期：Obsidian 插件 或 本地 Web 工作台
        ↓
长期：真实痛点证明需要时，再考虑薄专用 UI / 独立客户端
```

核心要求：**后台能力与界面解耦。**

Agent 是发动机，界面是驾驶舱，作品与知识资产才是长期资产。

---

# 5. 作者层不应该面对十几个 Skill

能力地图 C01–C20 是导航与路由地图，不是作者必须依次操作的 20 个 Skill。

作者只需感知大约 5–7 个工作阶段：

```text
1. 参考 / 研究
2. 构思作品
3. 规划故事
4. 写当前场景 / 章节
5. 审阅 / 诊断
6. 修改
7. 必要时：项目级重规划
```

后台专业能力不必都叫 Skill：

- Reader Sim：专业角色；
- Character Sim：专业角色；
- Canon：状态服务；
- Retrieval：基础设施；
- BookDistill：工作流；
- Writer：执行能力；
- Critic / Editor：评审模块；
- Controller：调度层；
- Knowledge Graph：数据结构 / 服务。

**Skill、Agent、角色、脚本、知识库、数据库、服务不能混成一个概念。**

---

# 6. 成熟作者完整能力地图：六个大区

2026-08-12 完整审查确认：当前不需要第七、第八个大区，也不需要扩成几十个固定技巧分类。

## 6.1 作品方向与判断

包括：

- 目标读者；
- 作品承诺；
- 题材与类型；
- 主题与 controlling idea；
- 审美目标；
- 作品究竟想成为什么；
- 市场/平台约束（相关时）。

## 6.2 故事运行能力

包括：

- 故事引擎；
- 结构；
- 人物；
- 关系；
- 世界；
- 信息；
- 悬念；
- 承诺与兑现；
- 长篇动力；
- 卷、章、场景；
- 因果与状态变化。

## 6.3 读者与文本效果

包括：

- 情绪；
- 注意力；
- 好奇；
- 期待；
- 欲望；
- 幽默；
- 恐惧；
- 审美；
- 运输感 / 沉浸；
- 流畅感；
- 微观动作 → 场景 → 章节 / 跨章的效果链。

## 6.4 页面写作能力

包括：

- 语言；
- 声音；
- POV；
- narrative distance；
- 对白；
- 潜台词；
- 感官；
- 动作 / micro-action；
- 细节；
- 意象；
- 留白；
- 句法和节奏。

## 6.5 判断与修订能力

包括：

- Reader Sim；
- Critic；
- Editor；
- Developmental Editing；
- Scene / Scene Turn；
- Character Architecture；
- Emotional Craft；
- Reveal Economy；
- 判断“为什么有效 / 为什么失效”；
- 修订优先级。

## 6.6 长期知识与创作运行能力

包括：

- 学习参考作品；
- Book Knowledge；
- Canon / Story State；
- Retrieval；
- Context Compiler；
- 作者意图；
- 写后回灌；
- Continuity；
- Controller；
- 系统长期成长。

## 6.7 永久开放入口

无论未来 taxonomy 怎样变化，都保留：

> **重要，但目前无法命名。**

分类是观察工具，不是发现边界。

---

# 7. 哪些应自主研发，哪些优先借鉴

| 能力 | 默认策略 | 优先借鉴 | AI-write 自己做 |
|---|---|---|---|
| SourcePrepare | 保留现有实现 | 现有工具链 | 输入协议、中文素材兼容 |
| 原著证据 / Discovery | 改造现有 BookDistill | ani-book、oh-story、creative-writing-skills、Apodictic、AI-Novel | 统一证据纪律、观察编排、总编辑收敛 |
| BookProfile | 组合成熟分析框架 | Apodictic、creative-writing-skills 等 | 蒸馏预算路由、置信度与不漏项约束 |
| BKP | **重点自定义协议** | Story Bible / Canon / KG / RAG schema 思路 | 多层粒度、证据、边界、检索标签、知识成熟度 |
| Story Bible / 人物 / 世界 | 优先借 | InkOS、NovelForge、graphify-novel、AuthorAgent 等 | 最小字段与写回接口 |
| 大纲 / 章 / 场景规划 | 优先借 | creative-writing-skills、oh-story、AI-Novel、ani-book 等 | 路由、中文长篇适配、Canon/KB 连接 |
| Writer | 优先借/改 | creative-writing-skills、oh-story、AI-Novel 等 | 上下文合同和项目适配 |
| Reader / Critic / Editor | 优先借 | creative-writing-skills、Apodictic、AI-Novel | 统一诊断格式和作者交互 |
| Continuity | 优先借 | InkOS、graphify-novel、ConStory 类分类等 | Canon 接口 |
| Canon / Memory | 优先借成熟架构 | InkOS、graphify-novel、NovelForge、AuthorAgent | 最小状态协议、确认后写回 |
| Retrieval / RAG / KG | 不自研底层搜索引擎 | 成熟检索/图查询实现 | 小说任务标签与小而相关的召回接口 |
| Cross-book Synthesis | **下一阶段关键胶水** | Muse / Planner / Context Compiler 思路 | 情境化综合、冲突/边界保留 |
| Controller / Router | **薄层自主实现** | Muse / Controller 类架构 | 作者友好的最小路由与确认机制 |
| UI | 暂缓 | Obsidian / Web 生态 | 只做真实痛点证明需要的薄界面 |

AI-write 自研应尽量集中在：

> **协议、路由、胶水、BKP、中文长篇适配、作者控制、必要状态接口。**

---

# 8. 原著蒸馏：目标是“创作智慧资产”，不是“漂亮总结”

## 8.1 当前 BookDistill 的真实定位

现有地基已经证明：

- 可以完整读取真实长篇；
- 可以 evidence-first；
- 可以保存 Fact / Inference / Observation / Pattern / Boundary 等不同层；
- 可以保留来源 fingerprint；
- 可以做章节、book_id、行号机械校验；
- 可以从跨章证据形成作者可读综合层；
- 可以生成 BKP 并被 KnowledgeRetrieve 消费。

但：“能运行、能生成、能检索”不等于“已经看见作品最值钱的东西”。

因此 BookDistill 的核心角色已经调整为：

> **总编辑：多视角发现 → 回源核证 → 整合 → 深挖 → 判断 → 压缩 → 封装 BKP。**

## 8.2 原著蒸馏的真正目标

> **尽可能发现并保存成熟作者真正会认为“值得学习、值得记住、以后创作可能重新调用”的作品精华。**

允许跨尺度发现：

- 宏观：结构、故事引擎、世界、长篇承诺；
- 中观：场景组合、情绪换挡、关系变化、信息推进；
- 微观：一句话、一个动作、一个称呼、一个省略、潜台词、感官、幽默、欲望、留白；
- 人物因果；
- 读者体验连续变化；
- 跨场景 / 跨章节累积效果；
- 难以命名但明显重要的创作智慧。

无法可靠抽象成 Pattern 的重要发现，应保留为有语境和证据的 Observation / Inference。

## 8.3 多视角 Discovery：G3 收口前正式确认

不是严格摘要流水线。

正式理解：

```text
SourcePrepare
    ↓
原著（最高事实源）
    │
    ├─ 默认镜头 A：长篇运行 / 读者动力
    │  └─ 优先借 oh-story + AI-Novel
    │
    ├─ 默认镜头 B：Reader / Page Craft
    │  └─ 优先借 creative-writing-skills
    │
    ├─ 必要时 Developmental Deep Dive
    │  └─ 优先借 Apodictic
    │
    └─ BookDistill 总编辑
       └─ 回源核证 → 去重 → 找组合效果 → 补边界/反例/置信度
    ↓
BookProfile / 必要追加 Deep Dive
    ↓
一个最终 BKP
```

约束：

1. **原著始终是最高事实源。**
2. **重要观察能力必须可以直接读取原著。** 不允许形成“摘要吃摘要”的永久信息损失链。
3. **BookProfile 是导航和预算工具，不是过滤器。**
4. 默认只需要两个互补发现镜头，不制造多个永久平级知识库。
5. Apodictic 式 Developmental 分析按问题触发，不要求每本书跑所有审计。
6. 允许一条 Observation 由不相邻句子、场景、章节共同支撑。
7. 允许“重要但难以命名”。
8. Discovery 可以宽，最终 BKP 必须克制。
9. 不围绕单个案例新增硬编码规则。
10. 本次修正是方法级，不要求重跑《一九八四》《三体》。

## 8.4 BookProfile 的正确位置

正确顺序：

```text
基础全书观察
→ BookProfile
→ 明确强项 / 潜在强项 / 普通项 / 不确定项
→ 1～N 次专项 Deep Dive
→ Profile 修正
→ BKP Finalize
```

BookProfile 负责分配后续蒸馏预算，不拥有永久删除某维度的权力。

必须允许“高价值全能型作品，需要增加蒸馏预算”。

## 8.5 一本书应该蒸馏几次

不设固定次数。

目标：

> 一部作品处理完成后，大部分未来有价值的知识已经进入固定 BKP；正式写作通常只检索，不重新蒸馏整本原著。

典型情况可以是：

- 普通 / 单项突出：基础 + 少量专项；
- 多项优秀：基础 + 2～3 次专项；
- 极高价值全能型：3～5 次甚至更多。

未来系统新增今天没有的重要观察能力时，允许旧书做“系统升级式再蒸馏”。

---

# 9. Book Knowledge Package（BKP）

## 9.1 它是什么

BKP 是一部参考作品最终进入 AI-write 的长期知识资产。

正常写作阶段只检索 BKP，不重新蒸馏整本原著。

它应该能回答：

- 这本书在哪些创作问题上值得参考？
- 它具体做了什么？
- 判断依据在哪里？
- 适用于什么情况？
- 有什么边界、反例和不确定性？

## 9.2 必须长期保留的核心知识

至少包括：

- 作品身份、source snapshot、版本、provenance；
- BookProfile；
- 作品地图；
- Observation；
- 重要 Inference；
- Work-specific Pattern；
- Deep Dive 高价值结果；
- Evidence 链；
- Scope；
- Boundary；
- Counterevidence；
- Confidence；
- 检索所需标签。

按作品需要，还可覆盖：

- 故事；
- 人物；
- 关系；
- 场景；
- 表达；
- 信息；
- 节奏；
- 世界；
- POV / 文体；
- 长篇连续性；
- 读者体验；
- 作品特有维度。

## 9.3 BKP 最难的不是文件格式，而是五件事

1. **粒度**：太粗是空泛总结，太细无法使用；需要多层知识共存。
2. **推断边界**：不能把单书观察变成普遍真理。
3. **跨书统一但不压平**：共用底座，同时保留不同题材和作品的独特知识。
4. **检索可用性**：未来从大量知识中只召回当前任务真正相关的一小部分。
5. **跨书归纳**：重复出现提高支持度，但出现次数多仍不等于永远正确。

---

# 10. 知识成熟度：绝不把单本书机制直接固化成定律

正式状态链：

```text
Source Evidence
    ↓
Observation / Inference
    ↓
Work-specific Pattern
    ↓
Cross-book Pattern
    ↓
Creation-tested Heuristic
    ↓
Production Rule
```

关键约束：

- 单本 BKP 内最高默认只到 Work-specific Pattern；
- 一本书不能自行证明普遍写作规律；
- 跨书重复只增加支持度；
- Production Rule 必须很少；
- 高层知识尽量保留来源、Evidence、适用条件、边界、反例、作品特异性、跨书支持度、真实创作验证状态和当前置信度。

这条纪律用于防止 AI-write 形成“AI 自己写出的教条”。

---

# 11. 真正写作时如何使用参考书知识

不是：

```text
写一个场景
→ 临时重蒸馏《三体》
```

而是：

```text
当前创作任务
+ 作者意图
+ Canon / 人物 / 关系 / 章节状态
+ 希望读者经历什么
        ↓
KnowledgeRetrieve
        ↓
少量相关 BKP Hit
        ↓
Context Compiler / Muse / Planner
        ↓
比较：互补？冲突？各自什么条件成立？
        ↓
1–3 个适合当前原创作品的方向
        ↓
作者选择 / 调整
        ↓
Writer / Scene execution
        ↓
Reader / Critic / Editor / Continuity
        ↓
作者确认修订
        ↓
State Writeback
```

Retrieval 的职责是**搬运正确的智慧**，不是替作者做最终综合。

---

# 12. G3 的正式结论

## 12.1 G3 已关闭

2026-08-12，作者确认：

**G3｜跨书知识库与创作任务检索正式退出。**

最终状态：

`G3_RETRIEVAL_VALIDATED / CLOSED`

完整记录：`00_项目控制/G3_收口记录_2026-08-12.md`。

## 12.2 G3 已证明

1. 《一九八四》《三体》两个正式 BKP 可以同时进入统一知识入口；
2. 真实创作问题可以跨书召回少量相关知识；
3. 返回结果数量受控；
4. 可追溯到作品、知识条目和必要 Evidence；
5. Scope / Boundary / Counterevidence / Confidence 可以保留；
6. 单书 Pattern 不会因为跨书检索自动升级成写作规则；
7. 对“偏单书 / 两书互补 / BKP 无答案”三类问题均完成验证；
8. 当前最小 KnowledgeRetrieve 足以证明技术链，不需要在 G3 内升级大型 RAG/KG。

结论维持：**NO_RAG_UPGRADE**。

## 12.3 G3 没有证明

关闭 G3 不等于：

- BKP 已捕获优秀作品全部精华；
- BookDistill 已是最终批量蒸馏器；
- 多书智慧已自动综合成最佳原创方案；
- Writer 已因 BKP 而显著提高原创质量；
- 当前关键词 / bigram 检索就是最终检索架构；
- 出现了新的 Production Rule。

这些不是 G3 尾巴，而是下一阶段的正式问题。

---

# 13. G3 之后明确存在的三个系统性问题

## 13.1 Discovery orchestration

问题：知识保存纪律较稳，但过去“怎样先看见真正重要的东西”偏薄。

状态：**G3 closeout 前已完成方法级修正。**

未来在新作品真实蒸馏时验证，不因此重跑旧书，也不因此继续扣住 G3。

## 13.2 Cross-book synthesis

状态：**未实现，正式留给 Phase E。**

未来由 Context Compiler / Muse / Planner 做情境化综合：

```text
作者意图
+ 当前 Story State
+ 读者目标
+ 少量跨书知识
→ 比较适用条件 / 冲突 / 互补
→ 给作者 1–3 个方向
```

禁止：

> “多数作品都这么写，所以它是真理。”

## 13.3 Author decision loop

状态：**未实现，正式留给 Phase E。**

目标：

```text
AI 给方案 / Evidence / 风险 / 推演
→ 作者做重大创作取舍
→ 系统按确认结果更新计划 / Canon / Story State
```

AI-write 最终应提高作者判断力，而不是把作者从创作决策里删除。

---

# 14. 核心长期上游参照

不以 star 数判断价值；按真实能力参照。

## oh-story

主要参照：

- 中文网文扫榜；
- 长/短篇拆文；
- 剧情单元；
- 情绪模块；
- 节奏；
- 文风；
- 对话潜台词；
- 期待/回报；
- 拆解资产回流卷纲/细纲/正文；
- 长篇追踪；
- 去 AI 味。

战略意义：中文商业网文“拆解 → 写作”的主要长期横向参照。

## creative-writing-skills

主要参照：

- Muse；
- Writer；
- Critic；
- Editor；
- Reader Sim；
- Character Sim；
- Outliner；
- Continuity；
- Writing Principles；
- Creative Writing Craft；
- Story Memory；
- Style Creator。

战略意义：专业创作团队、Reader Experience、页面 Craft、人物和编辑能力的核心参照。

## Apodictic

主要参照：

- Developmental Editing；
- contract / reader promise；
- Reader Experience；
- Character Architecture；
- Reveal Economy；
- Scene Turn；
- Emotional Craft；
- Decision Pressure；
- POV / Voice；
- Pacing / Rhythm；
- 多专项 Audit。

战略意义：成熟编辑如何观察、诊断并提升作者判断力。

## InkOS

主要参照：

- author_intent；
- current_focus；
- chapter intent；
- Context Compiler；
- future branch / narrative forecast；
- Canon / state；
- 写作 → 审计 → 修订 → 状态回灌；
- 运行时治理与作者确认。

战略意义：作者意图 + 当前状态 + 当前上下文 + 创作运行时。

## AI-Novel-Writing-Assistant

主要参照：

- 完整 AI Native 小说工作台；
- 拆书证据回溯；
- RAG；
- 写法资产；
- Reader Experience Contract；
- 书/卷/章/场景生产链；
- 自动导演；
- 审核 / 修复；
- 状态回灌；
- 长任务恢复；
- 桌面工作台。

战略意义：目前最接近 AI-write“完整工作台”目标的工程参照之一。

不整体照搬：它更强调帮助新手自动完成整本书；AI-write 更强调作者重大决策权。

## NovelForge

参照：结构化卡片、Schema、上下文注入、工作流、知识图谱、动态状态。

## graphify-novel

参照：Story Bible、派生 Knowledge Graph、chapter→bible 更新、跨章 thread / character / world tracking、source of truth 与派生图谱分离。

## ani-book-skill

参照：Codex 原生 Skill、Markdown/YAML 权威状态、确定性校验、章节稳定推进、作者确认后写入长期事实、可重建索引、evidence-first。

## 次级 / 按需候选池

NovelClaw、AuthorAgent、story-skills、novel-creator-skill、autonovel、Long-Novel-GPT、ConStory 类一致性项目、层级规划项目、书籍级信息抽取工具等继续保留。

### 参照池维护规则

出现以下情况时优先查看上游：

- AI-write 某项能力暴露真实不足；
- 准备进入新的重大阶段；
- 已借用项目明显升级；
- 当前方案开始需要大量自研规则；
- 作者真实创作出现新的长期痛点。

达到“候选足够成熟、差异清晰”后停止搜索，进入最小验证。

---

# 15. 创作后台的合理分层

## 作者看到

```text
参考 / 研究
→ 构思
→ 规划
→ 写
→ 审阅
→ 修改
```

## 后台参考层

- SourcePrepare；
- BookDistill；
- BKP Store；
- KnowledgeRetrieve。

## 作品状态层

- Project / Story Bible；
- Character / Relationship State；
- World / Rule State；
- Plot / Outline State；
- Foreshadowing / Thread State；
- Canon。

## 规划层

- Story Planner；
- Arc Planner；
- Scene Planner；
- Context Compiler；
- Cross-book Synthesis。

## 生成层

- Writer；
- Character Sim（必要时）；
- Style / Voice constraints。

## 审阅层

- Reader Sim；
- Critic；
- Developmental Editor；
- Continuity；
- Character consistency；
- Dialogue / pacing / information diagnostics。

## 修订与回灌层

- Editor / Revision；
- State diff；
- Canon / Story State writeback。

## 调度层

- Controller / Router；
- Author Decision Loop。

作者不需要自己决定“这次调用哪个后台模块”。

---

# 16. 当前开发路线

> 正式 Gate 是否切换仍由用户确认；本节只是长期路线。

## Phase A｜能力层成熟上游复查 —— 已完成阶段性目标

核心能力已有足够成熟候选；后续按真实问题触发更新，不无限搜索。

## Phase B｜BKP + BookProfile vNext —— 已完成阶段性目标

BKP v0.1 候选协议和 BookProfile 原则已建立，并被两种差异明显的作品验证可以容纳。

## Phase C｜BookDistill vNext 最小实现 —— 技术验证完成

已完成：

- 《一九八四》；
- 《三体》；
- Base Scan；
- BookProfile；
- 1～N Deep Dive 机制；
- BKP Finalize；
- evidence-first 地基。

后续只在真实使用暴露明确问题时升级。

## Phase D｜跨书知识库与检索 —— **已完成 / G3 CLOSED**

完成：

- 多 BKP 统一入口；
- 最小检索合同；
- KnowledgeRetrieve v0.1；
- 真实创作问题验证；
- 来源与边界保留；
- `NO_RAG_UPGRADE`；
- G3 closeout 前成熟作者完整能力审查与 Discovery 方法修正。

边界：只证明 Retrieval，不证明 Synthesis 和原创质量提升。

## Phase E｜创作核心后台 —— **下一长期方向，尚未正式立 Gate**

目标：优先组合成熟项目，而不是重新发明。

至少覆盖：

- Story / Project Bible；
- Canon / State；
- Context Compiler；
- Cross-book Synthesis；
- Outline / Scene planning；
- Writer；
- Character Sim；
- Reader Sim / Critic / Editor；
- Continuity；
- State Writeback；
- Controller；
- Author Decision Loop。

**Phase E 的第一步应该是 Borrow-first 组合设计，不是立刻写一个大系统。**

## Phase F｜创作沙盒

不直接拿正式长篇当试验品。

用可丢弃但真实的创作项目跑完整链：

```text
构思
→ 人物 / 世界
→ 大纲
→ 场景
→ 正文
→ 连续性
→ Reader / Critic
→ 修订
→ 状态写回
```

真正验收问题：

> **这些成熟能力组合以后，AI-write 能否持续写出“作者愿意继续看”的小说？**

先测试少量场景，再测试连续的小故事弧，不先测上百章。

## Phase G｜冻结 AI-write Production v1.0

满足最低生产质量后冻结稳定版：

- 正式写作使用稳定工具；
- 新能力在 shadow copy / 对照场景测试；
- 不直接在正在连载/长期创作正文主线上试验未验证新机制；
- 升级集中在开书前、卷末、大剧情节点等 checkpoint。

## Phase H｜正式长篇 + 面子演进

正式写作稳定后再判断：

- Obsidian 是否足够；
- 是否需要插件；
- 是否值得做本地 Web；
- 是否最终需要独立客户端。

不为了 UI 延迟真正写作能力建设。

---

# 17. Phase E 启动前的正确问题

G3 已关闭，下一阶段不能继续围绕 Retrieval 打转。

Phase E 启动前先回答：

1. 哪个成熟项目最适合作为 Story/Project Bible 与 Canon 基座？
2. Context Compiler 从 InkOS / AI-Novel / 其他项目借什么？
3. Cross-book Synthesis 应怎样消费 BKP Hits，同时保留冲突、适用条件和作者意图？
4. Planner / Outliner 如何结合 oh-story 的中文长篇读者动力与 creative-writing-skills 的探索能力？
5. Writer 是否直接基于成熟上游改造，而不是自研“超级 Writer”？
6. Reader Sim / Critic / Editor 如何组合而不重复？
7. Continuity 哪些交给确定性状态检查，哪些交给 LLM？
8. Author Decision Loop 如何保证 AI 给方案但作者掌握重大取舍？
9. 哪些东西需要持久化，哪些只是运行时派生上下文？
10. 最小创作闭环究竟需要哪些模块，哪些应该继续延后？

达到“组合方案足够清楚”后，再由作者确认下一 Gate。

---

# 18. 当前最重要的开放风险

## 18.1 原著 Discovery 方向已修正，但仍需真实新书验证

方法层已经补足：多视角直接读原著 + 总编辑收敛。

未来遇到新作品时验证即可；不因此重跑旧书、不因此重开 G3。

## 18.2 Cross-book Synthesis 尚未建立

这是 Phase E 的正式任务，不是 Retrieval 尾巴。

## 18.3 Author Decision Loop 尚未实现

长期哲学已明确，但运行时还需要真正实现作者确认、分支比较和状态写回。

## 18.4 超长网文与全能型作品尚未充分验证

包括：

- 数百章 / 数百万字；
- 低质量作品如何节省蒸馏预算；
- 多维都很优秀的全能型作品。

这些属于未来真实样本触发的回归条件，不阻塞当前路线。

## 18.5 长篇上下文成本

不能每次把全文、所有状态、几十本参考书和全部机制塞进模型。

必须依靠：

- Canon；
- 分层状态；
- Retrieval；
- Context Compiler；
- 任务相关知识召回。

## 18.6 AI 总结腔与“总钥匙”幻觉

持续用：

- Evidence；
- Counterevidence；
- Boundary；
- Scope；
- Confidence；
- 知识成熟度；

约束模型把复杂作品压成漂亮万能定律。

## 18.7 作者控制

必须区分：

- 自动机械检查；
- AI 建议；
- 作者必须确认的重大创作变化。

不可让自动审稿器替作者决定作品方向。

---

# 19. 当前禁止事项 / 防跑偏规则

1. 禁止现在批量蒸馏 60/141 本参考书。
2. 禁止用《一九八四》《三体》冻结最终 BKP schema。
3. 禁止单书 Pattern 直接升级为 AI-write 写作定律。
4. 禁止为了赶 Gate 跳过成熟上游复查。
5. 禁止把 C01–C20 一一做成作者操作的 Skill。
6. 禁止固定“每本书只能蒸馏两次”。
7. 禁止 BookProfile 在基础观察前裁掉未知维度。
8. 禁止正式创作日常触发整本参考书重蒸馏。
9. 禁止当前就开发完整独立写作软件。
10. 禁止因为开源项目整体很重，就忽略其中成熟局部能力。
11. 禁止为了自动化让作者失去重大创作决定权。
12. 禁止未经用户确认自动建立/退出 Gate。
13. 禁止自动覆盖/清理 Local Only、untracked 或不明来源本地变化。
14. 禁止为统一结构牺牲不同作品的独特性。
15. 禁止把“功能数量全面超过所有 GitHub 项目”作为目标。
16. 禁止 G3 关闭后继续为了工程完整度打磨 Retrieval。
17. 禁止无真实召回瓶颈就升级大型 RAG/KG。
18. 禁止把 Cross-book Synthesis 塞回 Retrieval，使 Retrieval 变成“超级大脑”。
19. 禁止 Phase E 一开始就自研全套 Writer/Canon/Reader/Editor/Continuity。
20. 禁止直接把正式长篇作为工具试验品。

---

# 20. Git 与资产安全

长期原则：

- 不自动清理不明来源的本地 dirty / untracked；
- 不覆盖 Local Only 资产；
- 不执行 `reset / restore / clean / force push / rebase / merge`，除非用户明确授权并确认风险；
- 远端少量文档修改可以由 ChatGPT 直接完成；
- 涉及本地大量文件、真实数据库、运行测试时优先交 Agent。

## 20.1 2026-08-12 GitHub 重复提交异常

通过 GitHub 连接器修改 `BookDistill/SKILL.md` 时，产生多条同名重复 commit。最终文件内容正确。

正式处理决定：

- 不 force push / reset / rebase 美化 main 历史；
- 这些提交只是历史噪音，不是待修故障；
- 不因此建立未来清理任务；
- 详细记录见 `G3_收口记录_2026-08-12.md`。

---

# 21. 阶段结束后的闭环更新机制

每个 Gate closeout 必须检查并同步：

1. 本手册；
2. `00_项目控制/当前工作索引.md`；
3. `00_项目控制/项目推进记忆.md`；
4. `00_项目控制/项目阶段门禁.md`；
5. `AGENTS.md`（仅长期规则变化时）；
6. 相关 STATUS / provenance / closeout 记录。

然后：

- commit；
- 报告 SHA；
- 明确“已证明 / 未证明”；
- 把下一阶段问题明确归属，不写成上一 Gate 尾巴；
- **没有用户确认，不自动切下一 Gate。**

如果长期目标、BKP 协议、作者工作流、关键上游、Borrow-first 边界或界面方向发生重大变化，也触发同样的记忆更新。

---

# 22. 当前状态快照

<!-- AUTO:CURRENT_STATE START -->
- G0：CLOSED。
- G1：CLOSED。
- G2：CLOSED。
- G3｜跨书知识库与创作任务检索：**`G3_RETRIEVAL_VALIDATED / CLOSED`，2026-08-12 由作者确认退出。**
- G3 已证明：多 BKP 可以小量、跨书、可追溯、有边界地服务真实创作问题。
- G3 未证明：BKP 精华绝对完整、跨书自动综合成功、原创 Writer 质量提升。
- G3 closeout 前已完成成熟作者六区能力审查和原著多视角 Discovery 方法级修正。
- 当前没有自动建立下一 Gate。
- 下一长期方向：Phase E｜创作核心后台。
- Phase E 启动前先做小型 Borrow-first 组合设计，由作者确认下一 Gate 后再实质开发。
<!-- AUTO:CURRENT_STATE END -->

<!-- AUTO:NEXT_ACTIONS START -->
## 下一步候选动作

1. 基于核心上游，形成 Phase E 最小组合方案：Story/Project Bible + Canon → Context Compiler / Synthesis → Planner → Writer → Reader/Critic/Editor → Continuity → State Writeback → Controller/Author Decision Loop。
2. 明确哪些能力直接借、哪些适配、哪些只借方法、哪些才是 AI-write 的真实剩余缺口。
3. 给出下一 Gate 的建议名称、唯一目标、最小退出条件、禁止范围。
4. 提交作者确认；确认前不开始大规模 Phase E 开发。
<!-- AUTO:NEXT_ACTIONS END -->

<!-- AUTO:OPEN_RISKS START -->
## 当前开放风险

- 多视角 Discovery 尚需在未来新作品上验证实际漏检改善程度；
- Cross-book Synthesis 尚未实现；
- Author Decision Loop 尚未实现；
- 超长网文 / 低质量作品 / 全能型作品边界尚未充分验证；
- 长篇 Context Compiler 必须控制上下文成本；
- 模型仍可能产生“总钥匙”式过度抽象；
- 多模块架构可能重新膨胀成作者操作工具堆；
- 未来任何 Retrieval 升级必须由真实召回瓶颈触发，而不是为了技术完整度；
- 正式创作开始前必须形成可冻结的最小 Production 工作流。
<!-- AUTO:OPEN_RISKS END -->

---

# 23. 重大决策摘要

## 2026-08-11｜原著蒸馏升级为长期知识资产

BookDistill 不再只是 pilot 总结工具；BKP 成为参考作品的长期固定知识资产。

## 2026-08-11｜BookProfile 不得预先裁剪未知强项

先基础全书观察，再用 Profile 分配后续专项预算。

## 2026-08-11｜蒸馏次数不固定

1 次基础 + 1～N 次专项；每次有明确价值即可。

## 2026-08-11｜知识必须分层

`Evidence → Observation → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

## 2026-08-11｜里子优先，面子延后

先做知识、状态、规划、写作、诊断、修订、Controller；独立 UI 等真实痛点证明需要时再做。

## 2026-08-11｜AI-write 自研范围收缩

成熟 Writer、Critic、Reader、Canon、Memory、Planning、Continuity、RAG/KG 等优先借；AI-write 重点做协议、路由、胶水、BKP、中文长篇适配、作者控制。

## 2026-08-12｜原著 Discovery 从单一 Base Scan 升级为多视角直接观察

确认两类默认镜头：长篇运行/读者动力；Reader/Page Craft。Apodictic 式 Developmental Deep Dive 按问题触发。BookDistill 作为总编辑收敛。

## 2026-08-12｜成熟作者完整能力地图确认六个大区

不继续扩 taxonomy；永久保留“重要但目前无法命名”。

## 2026-08-12｜G3 正式收口

`G3_RETRIEVAL_VALIDATED / CLOSED`。

G3 证明 Retrieval；Cross-book Synthesis 和 Author Decision Loop 正式归属 Phase E，原创质量验证归属 Phase F。

---

# 24. 一句话总纲

> **AI-write 的中心不是“知识越来越多”或“系统越来越严谨”，而是：从优秀作品中学到真正有价值的创作智慧，在当前原创作品的作者意图和故事状态下重新创造，用真实读者体验检验效果，并持续写回长篇状态；工程稳定保证下限，人物生命力、读者体验与审美能力决定上限。**
