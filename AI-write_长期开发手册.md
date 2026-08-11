# AI-write 长期开发手册

> 更新日期：2026-08-11  
> 文档定位：AI-write 根目录长期开发总纲，供作者、ChatGPT 与 Agent 共同阅读。  
> 当前正式门禁：**G2 已于 2026-08-11 由作者确认验收通过并正式退出；尚未建立下一 Gate。**  
> 当前战略状态：**Phase C 技术验证已完成；BookDistill vNext / BKP v0.1 进入稳定使用，后续只在真实样本或真实创作暴露明确问题时升级；不以工具完善本身为目标继续增加样本或功能。**

---

## 0. 这份手册为什么存在

AI-write 的长期风险不是“少做一个功能”，而是：

- 聊天里形成的重要判断没有写回项目，后续遗忘；
- 为了赶阶段而过早固化不成熟机制；
- 自己从零研发已经有成熟开源方案的能力；
- 把单本小说中的观察误写成普遍写作定律；
- 蒸馏几十本以后才发现知识粒度、结构或检索方式不对，被迫返工；
- 把作者变成系统操作员，让作者每天面对几十个 Skill、报告和配置项；
- 为了开发“面子”而耽误真正决定写作质量的“里子”。

因此，本手册负责记录：

1. 长期目标；
2. 已确认的核心原则；
3. 当前工作台架构；
4. 原著蒸馏与知识库设计方向；
5. 创作工作流设计方向；
6. 哪些应借鉴开源项目，哪些才值得自己研发；
7. 当前阶段、下一步与禁止事项；
8. 阶段结束后的自动更新规则；
9. 重大决策与其理由。

### 文档优先级

- **用户明确确认的最新意图永远最高。**
- `00_项目控制/` 中的当前门禁、当前工作索引和项目记忆仍是“当前执行状态”的权威记录。
- 本文件是根目录的长期架构与路线总纲，用于防止战略漂移。
- 如本文件与 `00_项目控制/` 的“当前状态”冲突：先停止自动推进，比较差异，再由用户确认后同步修正。

---

# 1. 终极目标

AI-write 不是“自动替作者生成一本小说”，也不是“把所有 GitHub 小说项目装进同一个仓库”。

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
Canon / Memory（作品事实与状态）
Retrieval（检索）
Context Compiler（上下文装配）
Character / Reader Simulation
Writer / Critic / Editor
Continuity
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
- 维护人物、关系、世界、伏笔和时间线；
- 从知识库中自动找相关经验；
- 规划故事与场景；
- 辅助正文；
- 做连续性、人物、节奏、对白、情绪、信息等诊断；
- 根据作者确认修订；
- 自动写回新状态。

---

# 2. 核心开发哲学

## 2.1 先借成熟智慧，再写自己的胶水

默认顺序：

```text
搜索成熟方案
→ 阅读其方法与实现
→ 判断可直接复用 / 可改造 / 只适合借鉴
→ 做最小真实测试
→ 吸收有用部分
→ 只有缺口仍然存在时才自主研发
```

原则：

- **Borrow-first，不重复造轮子。**
- 不因为项目不是为 AI-write 定制就忽略它；成熟局部机制可以拆下来使用。
- 不因为一个项目整体太重就放弃其中有价值的局部能力。
- 不把“我们自己想出来的规则”自动视为更适合 AI-write。
- 当前私人/非商业研究阶段，许可证不作为技术候选的淘汰条件；但来源、许可证、commit/provenance 仍要保留，未来公开、商用、服务化或分发前重新审计。

## 2.2 真实任务优先，但不是所有基础设施都等到正式小说再做

普通能力：

> 真实创作暴露问题 → 能力地图定位 → 候选项目 → 最小测试 → 吸收或放弃。

但两类基础设施不能过度“边写边补”：

1. **原著知识资产体系**：如果批量蒸馏后才发现 schema/粒度错误，会大规模返工；
2. **正式长篇生产的核心状态结构**：如果 Canon / 状态回写 / 上下文编译太晚确定，会污染正式作品。

因此：先建立“够稳的地基”，再进入正式长期生产。

## 2.3 作者不是机器

工作台不能要求作者：

- 手动选择十几个 Skill；
- 天天审核几十份报告；
- 记住所有伏笔状态；
- 严格服从大纲；
- 为了系统一致性牺牲突然出现的好创意。

正确行为：

```text
作者偏离计划
→ 系统识别影响
→ 告诉作者会改变什么
→ 作者确认
→ 更新大纲 / Canon / 后续状态
```

系统服务作者，而不是作者服务系统。

## 2.4 三方协作分工

AI-write 的日常开发由三方协作完成，各有明确职责边界：

**ChatGPT**：

- GitHub 调研、多项目比较、架构综合；
- 路线判断与方案建议；
- 远端少量复核。

**Agent（本地）**：

- 本地大量文件读取与代码检查；
- 运行测试、实现代码；
- 本地 Git 操作与 Benchmark。

**作者**：

- 主要判断创作效果和重大产品取舍；
- 不承担代码、schema 或复杂技术设计判断。

原则：

- 作者不需要理解实现细节，只需要判断"效果对不对"；
- ChatGPT 与 Agent 负责把方案做到可运行、可验证；
- 任何重大路线变化必须经作者确认，不得由 AI 方自行决定。

---

# 3. "里子"和"面子"必须分离

## 3.1 里子：真正决定能力的后台

优先开发：

- BookDistill / Book Knowledge；
- Canon / Memory；
- Retrieval；
- Context Compiler；
- Planning；
- Writer；
- Critic / Reader / Editor；
- Continuity；
- Controller / Router。

## 3.2 面子：作者最终从哪里使用

近期不急于做独立软件。

推荐演进：

```text
当前开发阶段：Agent + Markdown/Git
        ↓
近期作者工作：Agent + Obsidian
        ↓
中期：Obsidian 插件 或 本地 Web 工作台
        ↓
长期：如果真实使用证明需要，再考虑薄专用 UI / 独立客户端
```

核心要求：**后台能力必须与界面解耦。**

理想结构：

```text
作者界面（Obsidian / Local Web / Future UI）
                    ↓
             AI-write Controller
                    ↓
 Book Knowledge / Canon / Retrieval / Writer / Critic ...
                    ↓
          统一的本地接口 / 服务层
                    ↓
      Codex / Qwen / DeepSeek / 其他模型
                    ↓
          Markdown + 数据库 + Git
```

Agent 是发动机，界面是驾驶舱，作品与知识资产才是长期资产。

---

# 4. 作者层不应该面对十几个 Skill

之前“每个能力做一个 Skill”的思路过重。

能力地图 C01–C20 是**导航和路由地图**，不是作者需要依次操作的 20 个 Skill。

更合理的是作者只感知约 5–7 个工作阶段：

```text
1. 参考 / 研究
2. 构思作品
3. 规划故事
4. 写当前场景 / 章节
5. 审阅 / 诊断
6. 修改
（7. 必要时：项目级重规划）
```

后台可存在很多专业模块，但不必都叫 Skill：

- Reader Sim：专业角色；
- Character Sim：专业角色；
- Canon：状态服务；
- Retrieval：基础设施；
- BookDistill：工作流；
- Draft Writer：执行 Skill；
- Critic / Editor：执行或评审模块；
- Controller：调度层；
- Knowledge Graph：数据结构/服务。

**Skill、Agent、角色、脚本、知识库、数据库、服务不能混成同一个概念。**

---

# 5. 目前哪些应该自主研发，哪些优先借鉴

> 以下为当前路线，不代表已经全部完成实测。新发现项目在正式吸收前仍需证据化审查。

| 能力 | 默认策略 | 优先借鉴方向 | AI-write 真正需要自己做的部分 |
|---|---|---|---|
| SourcePrepare | 保留现有实现 | 现有工具链 | 项目输入协议、中文素材兼容 |
| 原著证据提取 | 改造现有 BookDistill | ani-book、oh-story | 统一输入输出与证据协议 |
| BookProfile | 组合成熟分析框架 | Apodictic、creative-writing-skills、能力地图等 | 蒸馏预算路由、置信度与“不漏项”规则 |
| Book Knowledge Package | **重点自定义协议** | Story Bible、Canon、KG、RAG schema 思路 | 多层粒度、证据、边界、跨书状态、检索标签的统一协议 |
| 人物 / 世界 / Story Bible | 优先借 | InkOS、NovelClaw、NovelForge、AuthorAgent、graphify-novel 等 | 适配 AI-write 的最小字段与写回 |
| 大纲 / 章节 / 场景规划 | 优先借 | creative-writing-skills、story-skills、层级规划类项目 | 路由、中文长篇适配、与 Canon/KB 连接 |
| 正文 Writer | 优先改成熟方案 | creative-writing-skills、oh-story 等 | 上下文编译与 AI-write 输入合同 |
| Critic / Editor / Reader | 优先借 | creative-writing-skills、Apodictic 等 | 统一诊断结果格式、作者交互 |
| 连续性检查 | 优先借 | InkOS、NovelClaw、ConStory 类分类、graphify-novel 等 | 与 AI-write Canon 的连接 |
| Canon / Memory | 优先借成熟架构 | InkOS、NovelClaw、AuthorAgent、NovelForge | 最小状态协议、作者确认后的状态写回 |
| 检索 / RAG / KG | 不自研底层搜索引擎 | 成熟 RAG/KG/图查询实现 | 针对小说创作的召回标签与上下文选择 |
| Controller / Router | **薄层自主实现** | Muse/Controller 类架构 | 把现有能力串成作者友好的最小流程 |
| UI | 暂缓 | Obsidian / Web 生态 | 只做真正被使用痛点证明需要的薄界面 |

核心目标：

> AI-write 自己研发的东西应尽量集中在“协议、路由、胶水、中文长篇适配、作者控制”，而不是重新发明别人已经做成熟的底层能力。

---

# 6. 原著蒸馏：从“总结一本书”升级为“固定知识资产”

## 6.1 当前 BookDistill v0.1.1 的真实定位

现有版本已经证明：

- 可以完整读取真实长篇；
- 可以做 evidence-first；
- 可以保存 FACT / INFERENCE / MECHANISM / BOUNDARY；
- 可以从大量逐章证据收口为跨章观察；
- 可以做来源 fingerprint、章节和行号机械校验。

这部分是值得保留的地基。

但当前版本的问题也已经暴露：

- 过度偏向“全书高度总结”；
- 容易把大作品压缩成十几条整齐机制；
- 人物、关系、场景、对白、情绪、叙事、语言等细粒度知识容易被压掉；
- 单书机制容易被写成过度确定的“写作规律”；
- 还不能保证一本书处理完成后，正式创作时无需重新蒸馏。

因此：**当前 BookDistill 不是废弃，而是 vNext 的证据地基。**

---

# 7. BookProfile 的正确位置

BookProfile 不能在读书前快速判断“这本书只值得蒸馏哪几项”，否则会漏掉未知强项。

正确流程：

```text
完整全维度基础蒸馏
        ↓
形成 BookProfile
        ↓
判断：
- 明确强项
- 潜在强项
- 普通项
- 暂不确定项
        ↓
决定哪些维度值得专项深挖
        ↓
专项结果反过来修正 Profile
```

BookProfile 的职责是：

> **分配后续蒸馏预算，而不是决定哪些维度可以永久忽略。**

每个维度至少要记录：

- 当前价值判断；
- 支撑证据量；
- 判断置信度；
- 是否存在反例；
- 是否值得专项深挖；
- 尚未确认而不是直接判定“差”。

如果一本书几乎所有维度都优秀，BookProfile 必须允许结论是：

> **“高价值全能型作品，需要增加蒸馏预算。”**

不能人为只选三项。

---

# 8. 一本书应该蒸馏几次

不设固定次数，也不追求最低次数。

工程目标是：

> 处理完成后，作品的大部分可用写作知识已进入固定知识包；正式写作通常只检索，不重新蒸馏原著。

建议结构：

```text
Pass 1：全维度基础蒸馏（所有书必做）
        ↓
BookProfile
        ↓
Pass 2+：按作品强项 / 不确定项做专项深挖
        ↓
交叉验证、去重、连接
        ↓
Book Knowledge Package 封装
```

典型情况：

- 普通/单项突出作品：1 次基础 + 1 次专项；
- 多项优秀作品：1 次基础 + 2～3 次专项；
- 极高价值全能型作品：3～5 次甚至更多也可以；
- 次数没有硬上限，前提是每次都解决明确且有价值的问题。

**不允许为了“快”强行把一本复杂作品压成一次。**

同时也不允许正式写作时因为当前场景需要某技巧，就临时重新蒸馏整本原著。

例外：未来系统出现今天没有定义的新能力维度时，可以对旧书进行“系统升级式再蒸馏”。

---

# 9. Book Knowledge Package（BKP）

## 9.1 它是什么

BKP 是一本书最终进入 AI-write 的固定知识资产。

目标不是制造漂亮总结，而是让未来写作任务可以可靠检索：

> “这本书在哪些创作问题上有值得调用的经验？依据是什么？什么时候适用？什么时候不适用？”

## 9.2 当前候选知识层

不是最终 schema，先作为设计方向：

```text
作品身份与来源
├─ source snapshot / fingerprint
├─ 版本信息
└─ provenance

作品画像 BookProfile
├─ 类型 / 题材
├─ 强项 / 潜在强项
├─ 不确定项
└─ 蒸馏覆盖度

故事层
├─ story engine
├─ macro structure
├─ arcs / escalation
└─ state changes

人物层
├─ character construction
├─ character arcs
├─ psychology
└─ decision patterns

关系层
├─ relationship states
├─ power / intimacy / conflict changes
└─ relational turning points

场景层
├─ scene patterns
├─ scene turns
├─ entrances / exits
└─ consequence chains

表达层
├─ emotion transmission
├─ dialogue / subtext
├─ action / micro-action
└─ reader inference

信息层
├─ information release
├─ suspense / mystery
├─ foreshadowing / payoff
└─ misdirection / delayed reveal

节奏层
├─ pacing
├─ chapter hooks
├─ long-form retention
└─ pressure / relief

世界层
├─ world rules
├─ exposition
├─ setting-to-conflict
└─ texture

叙事 / 文体层
├─ POV
├─ narrative distance
├─ style / voice
├─ imagery
└─ multi-genre / form switching

长篇层
├─ continuity
├─ long-range callbacks
├─ recurring motifs
└─ memory across long spans

读者体验层
├─ curiosity
├─ tension
├─ surprise
├─ emotional impact
└─ expectation / reward

可迁移知识层
├─ observations
├─ patterns
├─ boundaries
├─ counterexamples
├─ prerequisites
└─ failure modes

证据层
├─ source refs
├─ chapter / line refs
├─ evidence types
└─ confidence

检索层
├─ Cxx tags
├─ task tags
├─ genre tags
├─ scene function
├─ emotion / relationship / information goal
└─ applicability
```

## 9.3 BKP 最难的不是文件格式，而是五件事

1. **粒度**：17 条太粗，899 条又太碎；需要多层知识共存。
2. **推断边界**：不能把单书观察变成普遍真理。
3. **跨书统一但不压平**：不同类型作品共用底座，同时保留作品独特知识。
4. **检索可用性**：未来必须从几千/几万条知识里找到当前任务真正相关的少量内容。
5. **跨书归纳**：同类模式在多书重复出现时提高支持度，但“出现次数多”仍不等于“永远正确”。

---

# 10. 绝不允许把单本书机制直接固化成写作定律

知识必须有等级。

建议状态链：

```text
Source Evidence
    ↓
Observation（作品内观察）
    ↓
Pattern Hypothesis（作品内模式假设）
    ↓
Cross-book Pattern（跨作品重复模式）
    ↓
Creation-tested Heuristic（真实创作中有效的经验）
    ↓
Production Rule（极少数长期确认后才可能进入）
```

例如：

> “《三体》中多次让个人选择承担文明级后果。”

可以是 Observation / Pattern。

不能直接变成：

> “优秀小说必须让个人选择决定世界。”

每条高层知识原则上应保留：

- 来源作品；
- 证据；
- 适用条件；
- 边界；
- 反例；
- 作品特异性；
- 跨书支持度；
- 真实创作验证状态；
- 当前置信度。

这条规则用于防止 AI-write 形成“AI 自己写的教条”。

---

# 11. 真正写作时如何使用参考书知识

未来不是：

```text
写一个场景
→ 临时重新蒸馏《三体》
```

而是：

```text
当前创作任务
→ Controller 理解任务
→ Retrieval 从 BKP / 跨书知识库中召回相关知识
→ 选择少量最相关机制/案例/边界
→ 交给 ScenePlanner / Writer / Critic
→ 创作
→ 作者判断
```

例如当前任务：

> “主角第一次意识到世界规则可能是假的。”

系统可以同时召回：

- 某书的异常→解释回收；
- 某书的认知崩塌场景；
- 某本网文的章节钩子；
- 某作品的角色特异性反应；
- 与当前人物关系、题材、节奏最匹配的边界条件。

知识库的目标是“按任务召回”，不是“存得多”。

---

# 12. 创作后台的合理分层

## 12.1 作者看到的最小流程

```text
参考 / 研究
→ 构思
→ 规划
→ 写
→ 审阅
→ 修改
```

## 12.2 后台可能调用的专业能力

### 参考层

- SourcePrepare
- BookDistill
- Book Knowledge Store
- KnowledgeRetrieve

### 作品工程层

- Project / Story Bible
- Character / Relationship State
- World / Rule State
- Plot / Outline State
- Foreshadowing / Thread State

### 规划层

- Story Planner
- Arc Planner
- Scene Planner
- Context Compiler

### 生成层

- Writer
- Character Sim（必要时）
- Style / Voice constraints

### 审阅层

- Reader Sim
- Critic
- Continuity
- Character consistency
- Dialogue / pacing / information diagnostics

### 修订层

- Editor / Revision
- State diff
- Canon writeback

### 调度层

- Controller / Router

作者不需要自己决定“这次调用哪个后台模块”。

---

# 13. GitHub 搜索策略必须随着架构升级而重新审查

不能假设 G0 时找到的候选永远足够。

当架构发生大变化时，应进行一次有边界的“能力层 GitHub 再搜索”。

当前需要正式重新审查的能力层：

1. 原著知识化 / 文学分析；
2. Story Bible / Canon；
3. 长篇规划；
4. Writer；
5. Memory；
6. Retrieval / RAG / KG；
7. Continuity；
8. Reader / Critic / Editor；
9. Context compilation；
10. Controller / author control。

每层目标：

- 找 2～4 个最值得看的成熟方案；
- 明确：可直接用 / 适配后用 / 只借方法 / 不适合；
- 记录真正缺口；
- **缺口才进入自主研发队列。**

当前已知值得继续复查的老候选包括：

- ani-book
- oh-story
- creative-writing-skills
- Apodictic
- NovelClaw
- InkOS
- NovelForge
- AI-Novel-Writing-Assistant
- AuthorAgent
- novel-creator-skill
- autonovel

近期新发现、尚待正式入池审查的方向包括：

- graphify-novel 类 Story Bible / KG 项目；
- story-skills 类轻量写作 Skill 组织；
- ConStory 类一致性分类/Benchmark；
- 长篇层级规划类项目；
- 书籍级实体/人物/引语抽取工具（语言适配需单独判断）。

**禁止无限搜索。** 一轮审查达到“每能力层已有足够成熟候选且差异清晰”后立即停止搜索，进入最小验证。

---

# 14. 当前开发路线（战略版）

> 正式 Gate 是否切换仍由用户确认；本节是长期路线，不自动修改门禁。

## Phase A｜重新审查 GitHub 能力层

目标：

- 不再以“某个 GitHub 项目整体好不好”为中心；
- 按工作台能力层重新搜索与复查；
- 对每层给出“借什么 / 改什么 / 自研什么”的清单。

退出条件：

- 关键能力层都有 2～4 个充分审查的候选；
- 自研缺口被缩小到协议、胶水、中文长篇适配等必要部分。

## Phase B｜定义 Book Knowledge Package + BookProfile vNext

目标：

- 决定多层知识粒度；
- 决定通用基础维度；
- 决定专项蒸馏如何扩展；
- 决定 evidence / observation / pattern / heuristic 状态；
- 决定检索标签与边界字段；
- 明确哪些字段必须，哪些只在相关作品出现时存在。

退出条件：

- 不再依赖单个 `model.md + mechanisms.md` 作为主要知识入口；
- schema 能容纳至少两种差异极大的作品而不强行压平。

## Phase C｜BookDistill vNext 最小实现 —— 技术验证完成

已完成：

- 复用 evidence-first 地基，增加全维度基础蒸馏 + BookProfile + 1～N 次专项深挖 + BKP Finalize；
- 《一九八四》（24 章，14 维度，3 次专项：信息控制/情绪·恐惧塑造/结构·失败结局）与《三体》（42 章，13 维度，3 次专项：科学概念进入剧情/悬念·读者认知/个体选择与文明后果）均已完整跑通 vNext 闭环；
- 两书专项选择明显不同，证明 Agent 基于作品证据自主选择而非套用；两次均为 1 Base + 3 Deep Dive 是各自边际收益判断结果，不是预设次数；
- BKP v0.1 候选协议已能容纳两种差异极大的作品，不强行压平；
- 62 项单元测试全部通过。

BookDistill 升级原则：

> **真实使用暴露明确问题后再升级，不以工具完善本身为目标。**

不再继续为完善工具而增加第三样本。不修当前已知但非阻塞的小体验问题。

### 尚未充分验证的边界（非阻塞，如实保留）

- 尚未真实验证数百章、数百万字级超长网文；
- 尚未专门验证明显普通/低质量作品是否会较早停止、节省蒸馏预算；
- 尚未专门验证"几乎所有维度都非常优秀"的全能型作品。

设计原则：Deep Dive 是"绝对创作价值判断"，不是维度排名竞争。如果一本书世界观 10 分，但人物、关系、结构、文体也都有高价值，不得因为世界观最强而忽略其他维度；BookProfile 应允许增加蒸馏预算。

这些属于未来真实样本触发的回归条件，不作为当前 Phase C 的阻塞条件。

## Phase D｜跨书知识库与检索

目标：

- 多本 BKP 可并存；
- 支持按创作任务检索；
- 支持跨书 pattern 支持度；
- 不自动把“出现频繁”提升成 Production Rule。

退出条件：

- 一个真实创作问题能召回少量相关、可追溯、有边界的知识；
- 不需要作者手动记住参考书和机制名。

## Phase E｜创作核心后台

目标：优先改造成熟项目，而不是重新发明。

至少覆盖：

- Story/Project Bible；
- Outline / Scene planning；
- Writer；
- Canon / state；
- Continuity；
- Reader / Critic / Editor；
- Context compiler；
- Controller。

## Phase F｜创作沙盒

不是直接拿正式小说当工具试验品。

使用可丢弃但真实的创作项目，跑完整链：

```text
构思
→ 人物 / 世界
→ 大纲
→ 场景
→ 正文
→ 连续性
→ 诊断
→ 修订
→ 状态写回
```

观察真正瓶颈，再回到能力地图和候选池补能力。

## Phase G｜冻结 AI-write Production v1.0

满足最低生产质量后冻结：

- 正式写作使用稳定版；
- 新能力在 shadow copy / 对照场景中测试；
- 不直接在正在连载/长期写作的正文主线上实验未经验证的新机制；
- 升级集中在开书前、卷/大剧情节点等 checkpoint。

## Phase H｜正式长篇 + 面子演进

正式写作稳定后再判断：

- Obsidian 是否已足够；
- 是否需要 Obsidian 插件；
- 是否值得做本地 Web 工作台；
- 是否最终需要独立客户端。

**不提前为了 UI 延迟写作能力建设。**

---

# 15. 当前最重要的技术/方法难点

## 15.1 蒸馏知识粒度

太粗：变成空泛总结。  
太细：无法检索和使用。

必须支持多层知识，而不是只选一个粒度。

## 15.2 AI 总结腔和“总钥匙”幻觉

模型倾向于：

- 把一本复杂作品压成一句漂亮总论；
- 使用“不是 A，而是 B”式过度整齐抽象；
- 找一个万能机制解释全书；
- 把描述性规律写成规范性规则。

需要 evidence、反例、边界、置信度和知识等级共同约束。

## 15.3 不同题材不被统一模板压平

系统必须同时能处理：

- 剧情强、文笔普通；
- 文笔强、剧情普通；
- 人物极强；
- 关系/情绪极强；
- 世界观极强；
- 连载节奏极强；
- 多项都优秀；
- 特殊叙事实验型作品。

统一的是协议，不是结论。

## 15.4 长篇上下文成本

不能每次写一章都把全文、几十本参考书和所有机制塞给模型。

必须依靠：

- 状态化 Canon；
- 分层记忆；
- 检索；
- context compilation；
- 任务相关知识召回。

## 15.5 真实作者控制

系统必须区分：

- 自动机械检查；
- AI 建议；
- 作者需要确认的重大创作变化。

不可让自动审稿器替作者决定作品方向。

## 15.6 可维护性

未来更换模型、Agent、界面时：

- Markdown/结构化数据仍可读；
- 核心知识不被平台锁定；
- provenance 可追溯；
- 模块可以单独替换。

---

# 16. 当前禁止事项 / 防跑偏规则

1. **禁止现在批量蒸馏 60 本。**
2. **禁止用《一九八四》《三体》两本就冻结最终 BKP schema。**
3. **禁止单书 Pattern 直接升级为 AI-write 写作定律。**
4. **禁止为了赶 Gate 跳过“成熟方案复查”。**
5. **禁止把 C01–C20 一一做成作者必须操作的 Skill。**
6. **禁止固定“每本书只能蒸馏两次”。**
7. **禁止 BookProfile 在基础蒸馏前裁掉未知维度。**
8. **禁止正式创作日常触发整本参考书重新蒸馏。**
9. **禁止当前就开发完整独立写作软件。**
10. **禁止因为某个开源项目整体很重，就忽略其中可以拆走的成熟能力。**
11. **禁止为了“自动化”让作者失去重大创作决定权。**
12. **禁止未经用户确认自动退出当前 Gate 或进入下一 Gate。**
13. **禁止自动覆盖/清理 Local Only、untracked 或不明来源本地变化。**
14. **禁止为了统一结构而牺牲不同作品的独特性。**

---

# 17. 阶段结束后的闭环更新机制

这份手册不应该靠人记得更新。

## 17.1 每个阶段 / Gate closeout 必须做的动作

Agent 在完成阶段收口时，必须同时：

1. `fetch/compare` 当前远端与本地状态，遵守 Git 安全规则；
2. 更新本手册中的：
   - 当前状态；
   - 已确认决策；
   - 已吸收项目/能力；
   - 当前难点；
   - 下一步；
   - 禁止事项（如有变化）；
3. 同步更新 `00_项目控制/当前工作索引.md`；
4. 同步更新正式 Gate 文档；
5. 同步更新项目记忆；
6. 必要时更新 `AGENTS.md` 中的长期防跑偏规则；
7. 一次 commit 或逻辑清晰的连续 commits 落库；
8. 报告：改了什么、为什么、commit SHA、当前 Gate；
9. **没有用户确认，不自动切到下一 Gate。**

## 17.2 架构重大变化也必须触发更新

即使没有阶段结束，只要用户和 Controller 确认下列事项变化，也应更新本手册：

- 长期目标改变；
- BookDistill / BKP 协议改变；
- 作者工作流改变；
- 关键 GitHub 候选进入/退出；
- “借 / 改 / 自研”的边界改变；
- 工作台界面方向改变；
- 新增重大禁止事项。

## 17.3 自动更新不是后台定时任务

这里的“自动”指：

> **把更新本手册写进每个阶段收口任务的 Definition of Done。**

这样不需要作者另外记得说“更新手册”。

---

# 18. 建议的机器可更新区

Agent 更新时优先修改固定小节，避免整篇重写造成漂移。

<!-- AUTO:CURRENT_STATE START -->
## 当前状态快照

- 正式 Gate：G2 已于 2026-08-11 由作者确认验收通过并正式退出
- 当前无正式活跃 Gate；下一阶段候选方向为 Phase D｜跨书知识库与检索，尚未正式立 Gate
- Phase C｜BookDistill vNext 最小实现：技术验证完成
- 已完成真实 BookDistill vNext：`book_0038 一九八四`（24 章 Base Scan + 3 次专项 + BKP Finalize）、`book_0065 三体`（42 章 Base Scan + 3 次专项 + BKP Finalize）
- 两书专项选择明显不同（信息控制/情绪/结构 vs 科学概念/悬念/个体选择），证明 Agent 基于作品证据自主选择；两次均为 1 Base + 3 Deep Dive 是各自边际收益判断结果，不是预设次数
- BKP v0.1 协议已能容纳两种差异极大的作品；最终 BKP 已发布到 `02_原著蒸馏/<book>/bkp/`
- BookDistill 进入稳定使用状态；升级原则：真实使用暴露明确问题后再升级，不以工具完善本身为目标
- 当前明确不做：第三本自动蒸馏、60 本批量、正式 G3、完整 UI、最终知识库冻结；不把单书 Pattern 升级为普遍规则
<!-- AUTO:CURRENT_STATE END -->

<!-- AUTO:NEXT_ACTIONS START -->
## 下一步候选动作

1. 《一九八四》与《三体》vNext BKP 已发布到 `02_原著蒸馏/<book>/bkp/`，可供后续创作检索；
2. 2026-08-11，作者明确确认 G2 验收通过，G2 正式退出；
3. 由作者根据当时成果定义下一 Gate（候选方向为 Phase D｜跨书知识库与检索，尚未正式立 Gate / 尚未开始）。
<!-- AUTO:NEXT_ACTIONS END -->

<!-- AUTO:OPEN_RISKS START -->
## 当前开放风险

- 尚未真实验证数百章、数百万字级超长网文；
- 尚未专门验证明显普通/低质量作品是否会较早停止、节省蒸馏预算；
- 尚未专门验证"几乎所有维度都非常优秀"的全能型作品；
- BKP 粒度设计不当造成后续批量返工；
- BookProfile 误判导致遗漏作品隐性强项；
- 自适应停止判断在两本作品上均为 1 Base + 3 Deep Dive，样本仍有限，跨书可重复性仍需更多差异样本验证；
- 三体 0036 巨型章（10115 行）证据密度不均，跨章引用须注意大跨度性质；
- 模型把单书观察写成普遍规律；
- 多模块设计重新膨胀成作者操作几十个 Skill；
- 过早做 UI；
- 未来检索精度不足，知识库变成"知识坟场"。
<!-- AUTO:OPEN_RISKS END -->

---

# 19. 重大决策记录

## 2026-08-11｜原著蒸馏从“pilot 工具”升级为“长期知识资产”

原因：

《三体》第二个真实样本证明，BookDistill 能跨书工作，但 `model.md + mechanisms.md` 作为最终产物压缩过强，无法代表长篇小说全部可学习维度。

决定：

- 暂停规模化；
- 保留 evidence-first 地基；
- 重新设计多层 BKP；
- 写作时主要检索固定知识，不临时重新蒸馏原著。

## 2026-08-11｜BookProfile 不得先于全维度基础蒸馏裁剪维度

原因：

如果快速扫描误判，会永久漏掉一本书未知但重要的强项。

决定：

- 所有书先做全维度基础蒸馏；
- Profile 用于分配后续专项预算；
- 全能型作品允许多维度都进入深挖。

## 2026-08-11｜蒸馏次数不固定

原因：

不同书的价值分布差异很大。

决定：

- 通常 1 次基础 + 1～N 次专项；
- 2 次以上完全允许；
- 只要求每次有明确价值，不追求形式统一。

## 2026-08-11｜机制必须有知识等级，不得直接固化为真理

原因：

作者担心 AI 自己写出的机制被系统误当成正式写作规则。

决定：

`Evidence → Observation → Pattern Hypothesis → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

严格分层。

## 2026-08-11｜工作台“里子”优先，“面子”延后

决定：

- 先把知识、状态、检索、规划、写作、诊断、修订的后台能力做稳；
- 近期可用 Agent + Obsidian；
- 中期评估 Obsidian 插件 / 本地 Web；
- 核心后台与界面解耦。

## 2026-08-11｜AI-write 自研范围收缩

决定：

优先从开源项目借：Writer、Critic、Reader、Canon、Memory、Planning、Continuity、RAG/KG 等成熟能力。

AI-write 主要自研：

- 协议；
- 路由；
- 胶水；
- Book Knowledge Package；
- BookProfile 预算逻辑；
- 中文长篇适配；
- 作者控制；
- 必要的状态接口。

---

## 2026-08-11｜《一九八四》BookDistill vNext 自适应多轮专项蒸馏闭环验证完成（沙盒）

原因：

Phase C 的核心流程（Base Scan → BookProfile → 选择专项 → 深挖后重新判断 → 继续/停止 → BKP Finalize）此前未在真实作品上跑通；本任务用《一九八四》验证“能否根据作品实际价值自主决定继续蒸馏什么、并在合适的时候停止”。

结果（事实，不代表 Phase C/G2 整体完成）：

- 1 次全维度 Base Scan（24 章，682 条证据，14 维度）+ 3 次专项深挖：信息控制（任务前已完成）、情绪/恐惧塑造、结构与失败结局；
- 每轮记录选择理由、已有知识与待解决问题，轮末做 CONTINUE/STOP 判断（Round 2 → CONTINUE，Round 3 → STOP）；
- STOP 理由：主要高价值强项（信息控制、恐惧塑造、失败结局）已有系统知识；剩余候选（人物/关系、世界观、Reader Experience 等）主要重复已有 Observation/Pattern，边际收益低；
- BKP 重新 Finalize：18 条单书 Pattern（P1–P18）、边界/反证保留、知识等级未升级；observations 245 / inferences 79 / mechanisms 29 无损失；
- 结论：1 次基础 + 1～N 次专项的自适应机制在《一九八四》上可行；“能自主决定继续什么、何时停止”得到初步支持，但跨书可重复性仍需《三体》对照验证。

未做（保持 G2 边界）：不进入 G3、不做跨书 RAG/Retrieval、不跑第三本、不处理《三体》、不修改 B02/B09、不提交 Git。

## 2026-08-11｜G2 / Phase C 技术收口

原因：

两本真实样本（《一九八四》《三体》）已完整跑通 vNext 闭环（Base Scan → BookProfile → 3 次自适应 Deep Dive → STOP → BKP Finalize），专项选择由各自证据驱动，BKP v0.1 协议均能容纳。

决定：

- Phase C 技术验证完成，BookDistill 进入稳定使用状态；
- 升级原则：真实使用暴露明确问题后再升级，不以工具完善本身为目标；
- 不再为完善工具增加第三样本；
- 不修当前已知但非阻塞的小体验问题；
- 最终 BKP 发布到 `02_原著蒸馏/<book>/bkp/`；
- G2 技术工作完成，等待作者确认退出；
- 如实保留未充分验证的边界（超长网文、低质量作品、全能型作品）作为未来回归条件。

## 2026-08-11｜《三体》BookDistill vNext 第二真实样本回归完成（沙盒）

原因：

验证“自适应多轮蒸馏”在差异极大的第二本作品上是否可重复——本任务必须让《三体》从头完整走一次 vNext 流程，且专项选择只能由《三体》自身证据驱动，不得套用《一九八四》的专项。

结果（事实，不代表 Phase C/G2 整体完成）：

- 1 次全维度 Base Scan（42 章，1139 条证据：899 条旧版证据移植 + 240 条新 OBSERVATION，13 维度）+ 3 次专项深挖：科学概念进入剧情、悬念/读者认知、个体选择与文明后果；
- 每轮记录选择理由、已有知识与待解决问题，轮末做 CONTINUE/STOP 判断（Round 1/2 → CONTINUE，Round 3 → STOP）；
- STOP 理由：三大签名维度已有系统知识（18 条单书 Pattern P1–P18）；剩余候选（文体/意象/情绪/节奏/关系/Reader Experience 等）主要重复或证据不足；
- BKP 重新 Finalize：observations 240 / inferences 181 / mechanisms 17 跨章 + 18 深挖 / boundaries 84 + 三轮反证，知识等级未升级；
- 与《一九八四》的本质差异：专项选择完全不同（世界观/悬念/个体选择 vs 信息控制/情绪/结构），证明 Agent 基于作品本身选择而非套用；两次均为 1 Base + 3 Deep Dive 是各自边际收益判断的结果，不是预设次数；
- 结论：自适应多轮蒸馏机制已获得两个不同真实作品的支持，足以进入 Phase C/G2 收口判断（仍需作者审阅与确认）。

未做（保持 G2 边界）：不进入 G3、不做跨书 RAG/Retrieval、不做正式跨书 Pattern 归纳、不跑第三本、不修改 B02/B09、不提交 Git。

## 2026-08-11｜G2 验收通过，正式退出

原因：

作者审阅并明确确认 G2 全部 8 项退出条件均已满足。

决定：

- G2 正式退出；
- Phase C 技术验证完成，BookDistill vNext / BKP v0.1 进入稳定使用；
- 后续只在真实样本或真实创作暴露明确问题时升级；
- 不继续为了完善工具而主动增加样本或功能；
- 不自动建立或启动 G3；
- 下一阶段候选方向为 Phase D｜跨书知识库与检索，但尚未正式立 Gate / 尚未开始。

## 20. 一句话总纲

> **先充分借鉴成熟开源智慧，把优秀小说可靠地转成可追溯、可检索、不过度固化的长期知识资产，再把这些知识、Canon、规划、写作、诊断和修订能力通过一个薄 Controller 连接起来；作者只面对真实创作，不面对工具堆。**
