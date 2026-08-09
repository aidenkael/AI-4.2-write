# GitHub AI 小说项目横向评估（第一轮）

> 调研日期：2026-08-08
> 调研目的：停止只从项目内部推演“应该有什么 Skill”，先把成熟开源实践作为外部基线，再决定 AI-write 应直接复用、二次改造、自研还是仅作 Benchmark。
> 当前阶段：第一轮候选池 + 核心仓库深挖。**本报告不调整现有八大顶层目录，不直接安装第三方 Skill。**

---

## 1. 本轮结论摘要

### 1.1 方向判断

AI-write 当前的八大目录与资料生命周期没有必要推翻；真正空缺的是：

1. `02_原著蒸馏` 尚未形成明确、可重复、可供下游消费的“蒸馏输出契约”。
2. `04_写作知识库` 尚未形成完整的长篇小说能力谱系与经过验证的机制卡。
3. `05_Skills与自动化` 尚未明确哪些能力应该由成熟上游承担、哪些应该由 AI-write 自研。
4. 缺少统一 Benchmark，因此目前无法证明“我们自己的 Skill”“某个高星项目”“某个模型”谁真正更好。

### 1.2 最重要的新判断

**不能把“高星”直接等价为“所有写作规则都更强”，但高星 + 活跃维护 + 测试/契约 + 明确许可证，是非常强的优先级信号。**

实际检查已经出现三个典型情况：

- `oh-story-claudecode`：高星、活跃、MIT、有大量测试/契约，工程成熟度很高；但正文技法中仍存在明显公式化规则，因此更适合作为“中文网文工程基线”，不能把全部文艺判断照搬。
- `Lorn.NovelWriteSkills`：覆盖面和资产分层非常强，但星数只有 100–200 区间，且存在固定“9.2+ 自评分硬门槛”等伪精确风险；证明“低星项目也可能有局部强机制，高覆盖也可能伴随过度工程”。
- `Apodictic`：稿件诊断方法非常强，但许可证是 CC BY-NC-SA 4.0；如果 AI-write 未来存在商业用途，就不适合直接纳入代码/文本依赖，只适合研究与独立重实现思路。

因此后续采用双评分：

- **社区/工程可信度**：stars、forks、活跃度、测试、issue/PR、版本维护、许可证。
- **创作能力有效性**：必须通过我们自己的盲测 Benchmark。

---

## 2. 评估方法

每个候选仓库至少按以下维度记录：

| 维度 | 问题 |
|---|---|
| 社区验证 | Star 是否足够高？是否只是刚发布的短期热度？ |
| 活跃度 | 最近是否持续提交？是否仍在维护？ |
| 工程质量 | 有无测试、状态机、恢复机制、契约、版本升级策略？ |
| 创作覆盖 | 只会生成正文，还是覆盖选题、结构、人物、章节、审稿、记忆？ |
| 长篇能力 | 是否真正解决几十万字后的状态漂移，而非只靠长上下文？ |
| 写作方法 | 是否有可解释的场景、人物、情绪、对白、节奏方法？ |
| 可诊断性 | 能否指出“为什么不好”，还是只有泛化评分？ |
| 人机协作 | 作者决定是否被保护？AI 建议是否会未经确认写入正史？ |
| 上下文效率 | 是否按任务取上下文？是否避免每次加载全书/全部规则？ |
| 许可证 | 能否直接复制、修改、商用？ |
| 中文网文适配 | 是否理解起点/番茄/晋江等连载语境？ |
| 文学深度 | 是否处理人物复杂性、内心、情绪传递、意象、潜台词？ |
| Benchmark 价值 | 是否适合作为比赛对手或评价器？ |

采用级别：

- **A：直接采用/上游依赖候选** —— 许可证清晰兼容，机制成熟，测试后可直接使用。
- **B：基于上游二次改造** —— 大体适合，但需中文网文/我们的工作流适配。
- **C：借架构独立实现** —— 机制值得学，但许可证、技术栈或产品边界不适合直接纳入。
- **D：Benchmark / 参考资料** —— 不进入运行链，只作为对照、评审或知识来源。

---

## 3. 第一轮核心仓库

### 3.1 worldwonderer/oh-story-claudecode

GitHub：https://github.com/worldwonderer/oh-story-claudecode

**社区信号**：2026-08-08 通过 GitHub stars qualifier 区间核验，当前处于 **5.2k–5.3k stars**。近期仍在密集提交与发布。

**许可证**：MIT。

**定位**：目前最强的中文网文 Skill 工程基线之一。

#### 强项

1. 已把中文网文生产拆成多个独立能力，而不是一个万能 Prompt：长篇写作、长篇拆解、扫榜、导入已有作品、审稿、去 AI 等。
2. `story-long-analyze` 已经明确“拆文到底产出什么”：黄金三章、逐章摘要、爽点、钩子、情绪流、节奏、人物、关系、世界、力量、势力、可复用机制等。
3. `story-long-write` 不是一次性生成全书，而是开书、扩纲、具体章节、日更、回炉等不同路由。
4. 最近版本明显在处理真正的 Skill 工程问题：
   - 缩短热路径 SKILL，把一次性开书内容移入按需 references；
   - 删除重复/冲突规则，避免 Prompt 过长反而降低写作质量；
   - 用测试锁定不同运行端的行为一致性；
   - 长篇追踪从不断膨胀的 Markdown 状态，转成结构化单一权威状态 + 确定性派生视图，控制每章上下文成本。
5. Review 使用 PASS/WARN/FAIL + S1–S4 finding，不依赖一个虚假的“总分 9.6”。

#### 明显局限

1. 一部分正文技法仍偏模板化。例如“身体细节替代情绪词”虽然强调示例不可照抄，但仍容易让模型落入“情绪 = 身体动作”的单层替换。
2. 存在某些强硬规则（例如固定事件密度、部分标点限制、动静配比），适合特定网文，但不应成为所有作品的通用文学规则。
3. 情感方法已有“核心情绪命题 → 缺口 → 受阻 → 触发 → 主角动作 → 意义变化/兑现”的有效框架，但对 POV 注意力、解释、判断、冲动、关系微变化等“情绪如何传给读者”的微观机制仍不够深。

#### AI-write 初步判断

- 工程与中文网文生产：**A/B 级核心基线**。
- 拆文输出契约：**优先借鉴**，很可能直接成为我们设计 `02_原著蒸馏` 的第一参照。
- 情感/文学/人物深层诊断：**不能只靠它**，需要其他体系补齐。

---

### 3.2 ExplosiveCoderflome/AI-Novel-Writing-Assistant

GitHub：https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant

**社区信号**：已核验 **>1.8k stars**，近期持续高频开发。

**许可证**：默认 AGPL-3.0-only，并另提供商业授权路径。

**定位**：目前非常成熟的“长篇小说生产系统 / Agent Runtime”参照。

#### 强项

1. 从一句话到作品方向、世界、角色、卷规划、章节任务形成完整链路。
2. 章节不是“写完即结束”，而是：生成 → 审核 → 修复 → 人物/事实/伏笔状态回写 → 下一章。
3. 把人物做成动态资产，能够区分已确认事实与待确认候选，而不是让模型一次分析就污染正史。
4. 具备 RAG、检索轨迹、知识文档、世界手册、角色台账、风格资产、模型路由。
5. 分析一本参考书时支持人物证据回溯、阶段演化扫描等，这对我们的原著蒸馏非常有价值。

#### 许可证影响

不建议直接把其代码复制进 AI-write，除非未来明确接受 AGPL 约束或单独取得商业授权。

#### AI-write 初步判断

- 产品/状态/Agent 架构：**C 级重点研究，独立实现**。
- 它的独立仓库 `ani-book-skill` 采用 Apache-2.0，反而更适合直接研究/复用 Skill 级流程。

---

### 3.3 ExplosiveCoderflome/ani-book-skill

GitHub：https://github.com/ExplosiveCoderflome/ani-book-skill

**许可证**：Apache-2.0。

**定位**：把上面大型 Runtime 的经验重新压成 Codex 原生长篇小说 Skill，和我们的方向高度接近。

#### 强项

1. 明确把模型创造性判断与确定性脚本分开：模型负责理解/规划/生成/审阅，Python 只做状态、验证、索引、冲突检测、导出。
2. 采用可编辑 Markdown + 小型 YAML 权威状态，SQLite 只作可重建索引。
3. 保护作者已经确认/编辑过的工件；上游重要决策改变时，下游标记 `stale`，而不是静默重写。
4. 完整链路：
   `idea -> novel brief -> story bible -> world and cast -> volume strategy -> volume skeleton -> beat sheet -> chapter plan -> context package -> chapter draft -> humanization revision -> review/repair -> continuity update`
5. 参考作品分析明确要求：冻结来源范围和指纹、区分全量/抽样、先做分段证据笔记、事实/推断/假设分离、保留反证、最后形成“机制卡”，而不是复制文本或模仿文风。

#### AI-write 初步判断

**A/B 级重点候选。**

它很可能比我们从零设计“原著蒸馏工作流”和“作品工程状态机”更值得优先作为上游基线。

---

### 3.4 haowjy/creative-writing-skills

GitHub：https://github.com/haowjy/creative-writing-skills

**社区信号**：当前约 **300–400 stars 区间**，2026-08-08 当天仍有提交。

**许可证**：Apache-2.0。

**定位**：创作认知角色拆分做得非常好，尤其适合作为 AI-write 的“作家工作室角色架构”参照。

#### 强项

它没有堆一堆近似 Writer，而是明确区分：

- writer：正文
- critic：对抗性诊断
- editor：全局优先级
- reader-sim：模拟首次阅读的实际体验
- continuity-checker：正史一致性
- brainstormer：发散
- outliner：结构
- character-sim：人物声音与关系压力测试
- style-creator：风格
- knowledge maintainer：事实/时间线/正史

尤其值得借鉴的两项：

**Reader Sim**：不是问“这段写得好吗”，而是跟踪读者在哪里投入、走神、产生什么问题、预测如何变化，并区分沉浸、美感、社会模拟、好奇预测、Flow 等阅读回报通道。

**Story Context**：不同 Agent 只加载真正需要的上下文。Writer 通常只需场景 brief、相关风格、前一场/关键前文、出场人物状态和词汇；Brainstormer 甚至不能塞太多历史，否则会变得保守。

**Character Sim**：角色只能从自己的知识、关系、情绪压力出发；可以误解、回避、防御、绕话，而不是从作者全知视角回答。这非常适合测试人物是否活着、对白是否属于人物。

#### AI-write 初步判断

**A/B 级重点候选。**

特别适合直接吸收 Reader Sim、Character Sim、上下文最小化、Memory/Kb 分离思想。

---

### 3.5 Narcooo/inkos

GitHub：https://github.com/Narcooo/inkos

**社区信号**：已核验 **>1k stars**。

**许可证**：AGPL-3.0。

#### 强项

1. 长篇、短篇、剧本、互动故事统一在 Agent 工作台中。
2. 长篇记忆采用 story state + Markdown 投影 + SQLite + session summary，并区分 protected/compressible 上下文。
3. 很值得借鉴的“剧情多线推演”：在不污染正史的情况下产生 2–5 条隔离未来，比较章节节拍、人物决定、预期变化、风险和作者意图，再选择一条作为候选计划。
4. 可把已有作品导入并逆向生成设定，再重放章节状态。
5. Review/Revision 分严格度，并支持备份、恢复、写锁、真实工具完成态。
6. 强调写作 Agent 动笔前查带来源的专业资料，而不是 Prompt 硬凑。

#### AI-write 初步判断

由于 AGPL：**C 级架构研究**。

最值得独立实现的是：隔离式剧情分支推演、protected/compressible 上下文、已有作品状态重建。

---

### 3.6 RhythmicWave/NovelForge

GitHub：https://github.com/RhythmicWave/NovelForge

**社区信号**：已核验 **>1k stars**，近期仍活跃。

**许可证**：AGPL-3.0。

#### 强项

1. Schema-first 卡片：角色、设定等不是散文式大段文本，而是有可验证结构。
2. 上下文注入 + 知识图谱，适合长篇状态管理。
3. 很重要的“提取预览 → 人工调整 → 确认写入”模式：章节里提取出角色动态、关系、场景、组织、物品、概念状态后，不自动污染权威数据。
4. Code-style Workflow 而不是复杂 DAG，理由是更线性、更便于 AI 生成/维护。
5. 风格规则可作为知识库独立注入，而不是焊死在一个超长 Prompt 中。

#### AI-write 初步判断

**C 级架构研究。**

它最值得我们借的是“正史写回需确认”和 Schema-first，而不是 UI 本身。

---

### 3.7 anotherpanacea-eng/apodictic

GitHub：https://github.com/anotherpanacea-eng/apodictic

**许可证**：CC BY-NC-SA 4.0。

**定位**：本轮看到最系统的“小说诊断体系”之一。

#### 强项

它不是简单说“人物不够丰满”，而是拆成可重复诊断：

- Scene Turn：Goal → Conflict → Outcome；Reaction → Dilemma → Decision；场景是否真正改变局势。
- Emotional Craft：Perception → Interpretation → Judgment → Impulse → Choice/Action → Consequence；情绪是否真正传给读者。
- Character Architecture：Wound / Lie / Want / Need / Fear / Defense / Core Value；并追踪人物主动决定与“剧情木偶”行为。
- Literary Craft：判断文风、意象、结构、潜台词是否真正承担叙事功能，还是漂亮墙纸。
- AI Prose / POV / Stakes / Decision Pressure / Worldbuilding / Mystery / Horror 等大量专项审计。

#### AI-write 初步判断

因为 NC-SA 许可证，不作为直接上游依赖。

**D 级 Benchmark + C 级独立重实现思想来源。**

它特别适合补齐我们最关心的：感情描写、气氛、微动作、人物内心、潜台词、文学表达的“诊断层”。

---

### 3.8 Lorn.NovelWriteSkills

GitHub：https://github.com/lornshrimp/Lorn.NovelWriteSkills

**社区信号**：2026-08-08 核验处于 **100–200 stars 区间**，不是“高星冠军”。

**许可证**：仓库根暂未检索到明确 LICENSE；在核清前视为**禁止复制**。

#### 强项

1. 非常接近 AI-write 的“写作资产库”方向：CommonSkills、题材 Skill、Prompt/SOP、Instructions、质检脚本。
2. 已经明确区分：作者文风蒸馏、作品蓝本蒸馏、题材×平台写作研究蒸馏。
3. 作品蓝本不是泛泛总结，而是章首模式、钩子轮换、回报间隔、节奏分布等。
4. 先做轻量人物/设定，再等总纲稳定后重建模，能显著降低返工。
5. 具备市场→初始化→竞对→蒸馏→架构→建模→生产→发行的完整分层。

#### 风险

1. 章节闭环非常重，强制读取/调用大量 Skill，可能制造上下文膨胀。
2. 用固定“综合评分 >9.2”作为硬放行线，在没有外部标定的情况下属于伪精确。
3. 一些流程有“为了流程完整而执行”的倾向，可能反过来压制创作灵活性。

#### AI-write 初步判断

**C/D：架构与覆盖检查很有价值，不应整套照搬。**

尤其适合拿来检查我们“还有什么环节没想到”，而不是拿它的所有门禁当规范。

---

### 3.9 PenglongHuang/chinese-novelist-skill

GitHub：https://github.com/PenglongHuang/chinese-novelist-skill

**社区信号**：已核验 **>1k stars**。

**许可证状态**：README 展示 MIT badge，但本轮通过仓库 API 没有找到根 `LICENSE`，也未搜到 MIT 正文；在核清前按**许可证不明确**处理。

#### 强项

- 新手上手门槛低。
- 偏好记忆、中断恢复、多 Agent 写作模式、章节自动校验。
- 内置钩子、人物、对话、情节结构等指南。

#### 风险

“每章必爽”“开头即高潮”“每章结尾必须钩子”等规则适合作为某些商业网文策略，不应上升为优秀长篇小说通则；否则很容易得到机械化情绪曲线。

#### AI-write 初步判断

**D 级 Benchmark。**

用它测试“高自动化网文流水线能做到什么”，但不把其核心规则当我们的上限。

---

### 3.10 THU-KEG/StoryWriter

GitHub：https://github.com/THU-KEG/StoryWriter

**定位**：学术型多 Agent 长故事生成框架。

#### 强项

- Outline Agent 产生事件与事件关系。
- Planning Agent 把事件组织成章节计划。
- Writing Agent 动态压缩历史，按当前事件生成。
- 有人类与自动评估，并发布约 5000 篇长故事数据。

#### AI-write 初步判断

**D 级学术 Benchmark / C 级架构来源。**

它能证明“Outline → Planning → Writing + 动态历史压缩”是有实验支持的方向，但不能直接解决中文网文的商业阅读与文学表达。

---

### 3.11 GOAT-AI-lab/GOAT-Storytelling-Agent

GitHub：https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent

#### 强项

- 书级 specification → 章级 plot → scene 拆分 → scene 正文的自顶向下管线。
- Scene schema 已包含 Characters / Place / Time / Event / Conflict / Story Value / Value Charge / Mood / Outcome。
- 发布 20 篇自动生成 novella 作为可检查样本。

#### AI-write 初步判断

**D 级生成架构 Benchmark。**

适合检验“scene 是否应该有 Story Value/Outcome”这种结构思想，不适合直接当中文正文模板。

---

### 3.12 howells/fiction

GitHub：https://github.com/howells/fiction

**许可证**：README 声明 MIT（后续仍需单独核 LICENSE 文件）。

#### 强项

- 26 个专业 Agent：architect、writer、outliner、character developer、world builder、chapter reviewer、continuity、scene analyzer、voice analyzer 等。
- 完整的 Foundation → Draft → Review/Revise → Polish → Manuscript Critique → Publish Prep。
- 50k+ 作品使用并行 reader 做事实抽取与综合。

#### 风险

其中存在以具体作家名字命名的 critic persona。AI-write 不应该建立“模仿某个活着/具体作家风格”的核心机制；应抽象为通用评审维度。

#### AI-write 初步判断

**B/C：Agent 分工和并行阅读值得借鉴，具体人格化模仿不采用。**

---

## 4. 当前能力矩阵（第一版）

评分：`★★★` 当前强项；`★★` 有明确能力；`★` 较弱/只覆盖表层；`—` 不是重点。

| 能力 | oh-story | ani-book-skill | creative-writing | InkOS | NovelForge | Apodictic | Lorn | 当前 AI-write |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 中文网文连载 | ★★★ | ★★ | ★ | ★★ | ★★ | ★ | ★★★ | ★ |
| 原著蒸馏 | ★★★ | ★★★ | ★ | ★★ | ★★ | ★★诊断 | ★★★ | 骨架 |
| 市场/竞对 | ★★★ | ★★★ | — | ★★ | ★ | — | ★★★ | 有资料未体系化 |
| 长篇状态管理 | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★ | ★★ | 骨架 |
| 人物心理诊断 | ★★ | ★★ | ★★★ | ★★ | ★★ | ★★★ | ★★ | 弱 |
| Character Sim | ★ | ★ | ★★★ | ★★ | ★★ | — | ★ | 无 |
| 情绪传递诊断 | ★★ | ★★ | ★★ | ★★ | ★ | ★★★ | ★★ | 无 |
| 微动作/身体语言 | ★★偏公式 | ★ | ★★ | ★ | ★ | ★★★诊断 | ★★ | 无 |
| 对话潜台词 | ★★ | ★★ | ★★★ | ★★ | ★ | ★★★ | ★★ | 弱 |
| 场景转折诊断 | ★★ | ★★ | ★★ | ★★ | ★★ | ★★★ | ★★ | 无 |
| Reader Simulation | ★ | ★ | ★★★ | ★★ | ★ | ★★ | ★★ | 无 |
| 连续性/Canon | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★审计 | ★★ | 骨架 |
| 上下文最小化 | ★★★ | ★★★ | ★★★ | ★★★ | ★★ | ★★ | ★ | 未成型 |
| 正史写回保护 | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | — | ★★ | 未成型 |
| 多分支剧情推演 | ★ | ★★ | ★★★脑暴 | ★★★ | ★★ | — | ★ | 无 |
| 文学性/意象/潜台词 | ★★ | ★★ | ★★★ | ★★ | ★ | ★★★ | ★★ | 有文学素材未体系化 |
| 去 AI/文字自然 | ★★★网文向 | ★★ | ★★★ | ★★ | ★★ | ★★★诊断 | ★★★ | 未成型 |
| Skill 工程测试 | ★★★ | ★★★ | ★★ | 产品测试 | 产品测试 | ★★★ | ★★ | 未建立 |

这张表的意义不是选“一个总冠军”，而是确定：**不同能力的冠军可能来自不同上游。**

---

## 5. AI-write 目前不应自研的东西

第一轮已经足以判断，以下能力不值得从空白重新设计：

1. **长篇状态机基本思想**：已有多个成熟实现可参考。
2. **Reader Sim / Character Sim 的基本角色定义**：creative-writing-skills 已经给出很好的起点。
3. **原著蒸馏“先证据、后结论、再机制卡”的流程**：ani-book-skill 已经非常接近我们需要的形态。
4. **中文网文拆文输出字段**：oh-story 已有成熟参照。
5. **章节结束后的连续性写回与权威状态/派生视图分离**：oh-story / ani-book / InkOS / NovelForge 已有充分经验。
6. **把 Skill 核心说明与按需 references 分离**：oh-story 的近期改造已经证明这是必要工程实践。

我们应该做的是选择、组合、适配、Benchmark，而不是重新发明名字不同但本质相同的版本。

---

## 6. AI-write 真正值得建立差异化优势的地方

### 6.1 “网文商业叙事 + 世界文学深层表达”的双蒸馏

现有项目大多偏其中一边：

- 网文项目擅长钩子、爽点、留存、连载；
- 文学诊断项目擅长人物、人性、潜台词、情绪、意象。

AI-write 已经拥有网络小说 + 世界文学两个素材池，应把两者当成不同能力源，而不是同一种“小说训练数据”。

### 6.2 中文情绪传递与关系描写

需要专门研究：

- POV 注意到了什么；
- 这个细节对他意味着什么；
- 他如何判断；
- 想做什么但为什么没做；
- 身体动作只是结果之一，不是全部；
- 关系中的权力、距离、信任、羞耻、欲望、亏欠如何微调；
- 环境/物件/沉默如何加入情绪传递。

这比“悲伤=叠衣服、愤怒=青筋”高一个层级。

### 6.3 中国语境下的生活/职业/制度质感

历史、官场、军队、职场、司法、医疗、商业、乡村、城市生活等专业资料可以让场景具备真实可居住感。这是很多通用小说 Skill 没有的资产优势。

### 6.4 真正的 Benchmark 体系

最终竞争力不能是“我们写了更多规则”，而应是：

> 同样的输入，AI-write 的组合在盲测中长期赢。

---

## 7. 下一阶段 Benchmark 设计

### B1：人物声音盲测

同一人物卡，比较：

- generic LLM
- creative-writing Character Sim
- oh-story
- AI-write 组合版

测试：不同人物的对白能否互换；压力下是否仍保持人格逻辑；是否泄漏全知信息。

### B2：情绪传递盲测

同一“吃醋但不愿承认”的场景，各系统生成 800–1200 字。

评估：

- 是否直接标情绪；
- 是否只靠 stock body tells；
- POV 注意力是否有选择；
- 解释/判断/冲动/选择链是否成立；
- 关系是否发生细微状态变化；
- 读者能否在不被告知的情况下读出核心情绪。

### B3：场景 Turn

给相同场景目标，看正文结束时：信息、关系、资源、危险、目标、身份、认知是否至少一项发生有效变化。

### B4：Reader Sim

同一章节由多种 Reader Sim 输出“哪里投入/走神/产生问题/期待变化”，再与真人阅读反馈对照，检查哪个模拟器最有预测力。

### B5：连续性

给系统 20–30 章和预埋的 20 个事实，再写下一章，检查：

- 人物知识边界；
- 伤势/物品/地点；
- 时间；
- 关系状态；
- 未回收伏笔；
- 是否发生未经确认的正史写回。

### B6：去 AI / 中文自然度

人为准备一批典型 AI 文本：

- 过度解释；
- 对称句；
- 套路化动作；
- 翻译腔；
- 伪文学碎句；
- 每个人说话都太清楚。

比较不同系统的修订是否真的变自然，而不是换一套 AI 腔。

### B7：原著蒸馏

从现有本地作品中先选 2 部网文 + 1 部世界文学做小样：

- 同样章节范围；
- 各系统独立分析；
- 比较谁能产出“可供后续写作消费”的机制卡，而不是书评。

**注意：Benchmark 使用原著只作内部研究，不重新分发原文。**

---

## 8. 第一轮暂定上游分工

不是最终决定，必须经过 Benchmark：

| AI-write 能力 | 当前第一候选 | 第二候选 / 对照 |
|---|---|---|
| 中文网文拆文 | oh-story | Lorn / ani-book |
| 原著蒸馏证据协议 | ani-book-skill | oh-story |
| 长篇状态/上下文 | oh-story + ani-book | InkOS / NovelForge |
| Reader Sim | creative-writing-skills | 自研 + Apodictic 思路 |
| Character Sim | creative-writing-skills | InkOS |
| 情绪诊断 | 独立重实现 Apodictic 思路 | oh-story 情绪引擎 |
| 场景诊断 | 独立重实现 Scene Turn 思路 | oh-story Review |
| 对话/潜台词 | creative-writing +专项对话项目 | oh-story |
| 文学性/意象诊断 | 独立重实现 Apodictic 思路 | 世界文学蒸馏 |
| 市场/竞对 | oh-story / ani-book | Lorn |
| Schema/正史写回 | ani-book | NovelForge |
| 剧情多分支推演 | InkOS 思路独立实现 | creative-writing brainstormer |
| 去 AI | oh-story + creative-writing | 独立中文语料 Benchmark |
| Skill 工程方法 | oh-story + ani-book | Anthropic Skills / 通用 Skill 工程项目 |

---

## 9. 许可证初步台账

| 仓库 | 许可证 | 直接纳入建议 |
|---|---|---|
| worldwonderer/oh-story-claudecode | MIT | 可作为 A/B 候选，保留版权/许可声明 |
| ExplosiveCoderflome/ani-book-skill | Apache-2.0 | 可作为 A/B 候选，按许可证履责 |
| haowjy/creative-writing-skills | Apache-2.0 | 可作为 A/B 候选 |
| ExplosiveCoderflome/AI-Novel-Writing-Assistant | AGPL-3.0-only + 商业授权 | 不直接复制代码，优先 C |
| Narcooo/inkos | AGPL-3.0 | 优先 C |
| RhythmicWave/NovelForge | AGPL-3.0 | 优先 C |
| anotherpanacea-eng/apodictic | CC BY-NC-SA 4.0 | D/C，不进入未来商业运行依赖 |
| lornshrimp/Lorn.NovelWriteSkills | 未核清 | 禁止复制，先研究 |
| PenglongHuang/chinese-novelist-skill | README 写 MIT，但根 LICENSE 未找到 | 核清前禁止复制 |

> 本台账只做项目工程筛选，不构成法律意见。真正 vendor/复制前必须再次核验目标版本的许可证与 NOTICE 要求。

---

## 10. 第二轮待深挖对象

第一轮之后，不再无边界搜索；第二轮集中到以下方向：

1. `oh-story`：继续拆 `story-review`、tracking、deslop、dialogue、reader-contract。
2. `ani-book-skill`：拆 book-analysis、artifact-contracts、generation-contracts、context package、recovery。
3. `creative-writing-skills`：拆 story-memory、story-review、writing-principles、critic/editor/continuity 工作协议。
4. `InkOS`：重点研究剧情分支隔离、protected/compressible context、旧书导入回放。
5. `NovelForge`：重点研究 Schema-first 和提取确认写回。
6. 学术体系：StoryWriter / GOAT / 其他带人评与自动评结果的长篇生成论文实现。
7. 中文网文其他 >1k star 项目：继续排除只做 UI/自动生成但缺乏可迁移方法论的仓库。
8. 通用 Skill 工程：Anthropic Skills / Superpowers 等，用来校准 Skill 如何拆、如何按需加载、如何测试，而不是学习小说知识。

---

## 11. 当前阶段结论

现在还不应该发布“AI-write 长篇小说能力地图 v1 正式版”。

当前正确顺序是：

```text
GitHub 候选池
    ↓
核心仓库逐文件解剖
    ↓
许可证/维护/工程成熟度筛选
    ↓
能力矩阵
    ↓
Benchmark 盲测
    ↓
确定每项能力的上游冠军
    ↓
AI-write 能力地图 v1
    ↓
再决定 02_原著蒸馏 / 04_知识库 / 05_Skills 的具体落盘方式
```

第一轮已经足以改变一个基本思路：

> **AI-write 不应该成为“我们自己写出的一整套小说 Skill”；它更应该成为“选择、验证、组合当前优秀开源能力，并用我们自己的网文 + 世界文学 + 中国专业资料建立差异化能力”的创作系统。**

下一阶段必须继续以证据和 Benchmark 为准，而不是因为某个仓库星数高、README 写得漂亮，就直接把它变成项目规范。
