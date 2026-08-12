# GitHub 候选池｜能力路由 v0.2

> 首建：2026-08-10  
> 最近校准：2026-08-12（G3 closeout 后）  
> 状态：**长期上游路由表**，与全局能力地图和长期开发手册配套使用。  
> 旧版 G0/G3 收口前内容已原样归档：`99_归档/GitHub候选池_能力路由_v0.2_G3收口前_2026-08-12.md`。

## 一、这份候选池怎么用

这不是“项目排行榜”，也不是“以后全部排队做 Benchmark”的清单。

默认流程：

```text
真实创作 / 蒸馏问题
→ 定位需要的能力
→ 看本表中最相关的 1～3 个成熟上游
→ 先理解其完整工作逻辑
→ 最小真实测试
→ 直接借 / 适配后借 / 只借方法 / 放弃
→ 只有剩余缺口才自研
```

长期原则：

1. **Borrow-first，不重复造轮子。**
2. 存在于候选池 ≠ 已经整体实测通过。
3. 某个方法/机制被验证 ≠ 整个仓库所有能力都已验证。
4. 不因为某项目整体很重就忽略其中成熟局部能力。
5. 不默认每项能力都建立严格 Benchmark；普通能力用少量真实任务快速判断。
6. 不以 star 数作为核心判断。
7. 当前私人研究阶段，许可证不作为技术候选淘汰标准；真正复制/修改时仍保留来源、上游 commit/tag、LICENSE 和改动范围。
8. 达到“成熟候选足够、差异清楚”后停止搜索，进入组合和最小验证。

---

# 二、核心长期横向参照

以下项目是当前 AI-write 最重要的长期能力参照。它们不是彼此竞争“总冠军”，而是承担不同能力层。

## 1. ExplosiveCoderflome/AI-Novel-Writing-Assistant

**当前定位：核心长期参照。**

主要能力：

- 一句灵感 → 书级方向 → 世界 / 角色 → 卷战略 → 章节任务 → 正文；
- 拆书证据回溯与角色深度分析；
- 拆书 / 知识库通过 RAG 回流规划、续写和正文；
- 写法资产进入生成、检测、修复；
- Reader Experience Contract：章节核心问题、承诺回报、主角即时欲望、阻力、转折、情绪/信息变化、章末净变化、继承钩子、追读钩子；
- Writer / acceptance / repair 消费同一读者体验合同；
- 事实、角色、伏笔、状态回灌；
- 自动导演、任务恢复、运行时治理、桌面工作台。

AI-write 应重点借：

- 完整“参考资产 → 创作”生产链；
- Reader Experience Contract 的运行时思想；
- 书 / 卷 / 章 / 场景分层；
- 写作后验收、修复、状态回写；
- 长任务恢复与上下文治理；
- 拆书资产不只是保存，而是真正进入后续写作。

不整体照搬：

- 其产品目标更偏“让不懂写作的新手自动完成整本书”；
- AI-write 更强调**重大创作决定由作者掌握**，AI 提供方案、证据、风险和推演。

当前证据状态：

- 已完成较深入代码/文档横向审查；
- 已作为 G3 closeout 能力地图核心参照；
- 未把整套产品原样接入 AI-write；
- 下一触发点：Phase E 的 Context Compiler、Planner、Reader Experience、生产链与状态回写设计。

## 2. worldwonderer/oh-story-claudecode

**当前定位：中文商业网文“拆解 → 写作”核心参照。**

主要能力：

- 扫榜选材；
- 长篇 / 短篇拆文；
- 黄金三章、逐章摘要、剧情单元；
- 情绪模块；
- 节奏 / 爽点 / 虐点 / 期待点 / 回报；
- 关键信息推进；
- 全书情绪节奏；
- 角色、世界、关系；
- 文风、对话潜台词；
- 拆文资产进入对标目录、卷纲、细纲和正文；
- 长篇追踪状态；
- 日更 / 续写 / 修订；
- 去 AI 味。

AI-write 应重点借：

- 长篇运行 / 读者动力 Discovery 镜头；
- “拆别人为什么有效 → 形成剧情/情绪/节奏资产 → 回到自己的规划和正文”的天然迁移链；
- 中文网文的期待 / 回报、压力 / 换气、章末钩子、剧情单元；
- 中文长篇实际生产纪律。

不整体照搬：

- 题材和商业网文方法不能被升级成所有小说的普遍写作规则；
- “验证过的模式”必须结合作者意图、题材、人物和当前作品状态重新创造。

当前证据状态：

- B02 / B09 曾实测其部分机制和拆文方法；
- G3 closeout 又重新审查其完整拆解→写作链；
- 已正式成为 BookDistill 默认“长篇运行 / 读者动力”观察镜头的重要方法来源；
- 下一触发点：Phase E Planner / 中文长篇读者动力 / Writer 组合。

## 3. haowjy/creative-writing-skills

**当前定位：专业创作团队 + Reader/Page Craft 核心参照。**

主要能力：

- Muse；
- Writer；
- Critic；
- Editor；
- Reader Sim；
- Character Sim；
- Brainstormer；
- Outliner；
- Continuity Checker；
- Style Creator；
- Story Memory；
- Writing Principles；
- Creative Writing Craft。

AI-write 应重点借：

- 作者只面对 Muse / 创作问题，后台自动路由专业角色；
- Reader Sim 的第一次阅读、逐时体验方法；
- reader reward channels：transportation、aesthetic、social simulation、flow、curiosity/prediction；
- 人物作为“心智”而不是设定卡的观察和模拟；
- 页面级语言、POV、潜台词、留白、节奏、感官等 Craft；
- Writer → Critic / Editor / Reader Sim → 再修订的反馈环。

不整体照搬：

- 不让作者手动管理大量 Agent / Skill；
- 不把风格学习变成机械模仿原作者。

当前证据状态：

- B02 曾实测其中部分机制；
- G3 closeout 已深入复查 Reader Sim / Writing Principles / 整体角色架构；
- 已正式成为 BookDistill 默认“Reader / Page Craft”观察镜头的主要方法来源；
- 下一触发点：Phase E Muse / Writer / Reader / Critic / Editor / Character Sim 组合。

## 4. anotherpanacea-eng/apodictic

**当前定位：Developmental Editing / 高层诊断核心参照。**

主要能力：

- contract / reader promise / controlling idea；
- Reverse Outline；
- Reader Experience；
- Structural Mapping；
- Character Audit / Character Architecture；
- Reveal Economy；
- Rhythm / Modulation；
- Emotional Value / Emotional Craft；
- Scene Function / Scene Turn；
- POV / Voice；
- Theme；
- Entity Tracking；
- Decision Pressure；
- 多种 genre / craft / tag audits；
- Revision Coach。

AI-write 应重点借：

- “作品真正承诺了什么，文本是否真的兑现”的观察方式；
- 成熟发展编辑的多镜头诊断；
- 当基础观察发现系统性问题时，按问题触发 Deep Dive，而不是每本书固定跑几十个检查；
- Firewall 思想：指出问题和解决方案类别，但不自动夺走作者创作权。

不整体照搬：

- 不把 40+ Audits 直接变成 AI-write 的固定 Skill 清单；
- 不要求每本参考书或每篇正文都全量跑完整 DE。

当前证据状态：

- B02 早期做过机制分析但未原样跑整个工具；
- G3 closeout 已对其当前 Audit Matrix、Reader Experience、Developmental Editing 体系做深入方法审查；
- 已正式进入 BookDistill 的“按问题触发 Developmental Deep Dive”方法来源；
- 下一触发点：Phase E Critic / Editor / Reader diagnosis 与作者判断环。

## 5. Narcooo/inkos

**当前定位：作者意图 + Context Compiler + Story State + 创作运行时核心参照。**

主要能力：

- author_intent；
- current_focus；
- chapter intent；
- Context Compiler；
- protected / compressible context；
- narrative forecast / 多未来分支；
- 分支比较：人物决策、风险、作者意图对齐；
- Canon / Story State；
- plan → compose → write → audit → revise → state settlement；
- 导入已有作品并回放状态；
- 写作任务恢复 / 并发治理；
- Skills 作为专业指导，但不能绕过工具权限和确认门。

AI-write 应重点借：

- 作者意图与当前 1–3 章 focus 的显式保存；
- Context Compiler；
- 多个未来分支先隔离推演，作者选中后只写计划，不提前污染 Canon；
- 正文之后 Observer / audit / revise / state writeback；
- “完成状态必须由真实工具结果和文件决定”，不能靠 AI 口头声称完成。

当前证据状态：

- 已多轮代码/架构审查；
- 已被确认是 Phase E Author Decision Loop 与 Context Compiler 的主要参照；
- 下一触发点：Phase E 最小创作后台组合。

## 6. RhythmicWave/NovelForge

**当前定位：结构化创作资产 / 工作流 / 上下文注入参照。**

主要价值：

- Schema 驱动卡片；
- 字段级结构化生成；
- 上下文注入 / DSL；
- Knowledge Graph；
- 动态状态；
- 可配置工作流；
- 工作流 Agent；
- 拆书工作流与 UI。

AI-write 应重点借：

- 结构化创作资产的组织方式；
- Context 注入与工作流可配置思想；
- Canon / Story State 与图谱/派生索引的接口思路。

下一触发点：Phase E Story Bible / Canon / Context / Workflow 设计。

## 7. Anshler/graphify-novel

**当前定位：Story Bible / Canon / 派生 Knowledge Graph 轻量参照。**

主要价值：

- 从已有章节建立 Story Bible；
- 人物 / 世界 / thread 跨章追踪；
- chapter → bible 更新；
- source of truth 与派生图谱分离；
- 多批次 fresh context 处理长篇；
- query / status / update。

AI-write 应重点借：

- Canon 作为权威、KG/索引作为可重建派生层；
- 跨章 thread / character / world tracking；
- 简单而透明的 Story Bible 结构。

下一触发点：Phase E Canon / Story Bible 候选比较。

## 8. ExplosiveCoderflome/ani-book-skill

**当前定位：evidence-first / 权威工件 / 确定性与 LLM 边界核心参照。**

主要价值：

- Codex 原生 Skill；
- Markdown / YAML 权威状态；
- Python 只负责确定性校验；
- 一章一章稳定推进；
- Continuity；
- 可重建索引；
- 作者验收后再进入长期事实；
- 授权文本拆解与证据约束。

AI-write 已吸收：

- BookDistill 的 evidence-first、来源追溯、事实/推断边界、确定性校验思想。

下一触发点：Phase E 权威状态 / Canon 写回 / 确定性校验边界。

---

# 三、Phase E 优先路由

下一阶段不是“再找更多项目”，而是用现有核心参照拼最小创作后台。

| Phase E 能力 | 首看上游 | 主要问题 |
|---|---|---|
| Story / Project Bible | graphify-novel、InkOS、NovelForge、ani-book | 什么是权威 Canon，什么是派生索引 |
| Canon / Story State | InkOS、graphify-novel、NovelForge、ani-book | 作者确认后的写回、状态差异、连续性 |
| Context Compiler | InkOS、AI-Novel、NovelForge | 当前章到底装哪些资料、如何控制成本 |
| Cross-book Synthesis | creative-writing-skills Muse、InkOS forecast、AI-Novel planning | 如何综合多书 Hit 而不制造普遍规则 |
| Planner / Outliner | oh-story、creative-writing-skills、AI-Novel、ani-book | 事件计划 + 读者体验 + 人物行动如何一起规划 |
| Writer | creative-writing-skills、oh-story、AI-Novel | 不自研超级 Writer；怎样消费统一 Context |
| Character Sim | creative-writing-skills | 人物声音、关系和决策测试 |
| Reader Sim | creative-writing-skills、Apodictic、AI-Novel | 感受信号 vs 分析诊断如何分工 |
| Critic / Editor | Apodictic、creative-writing-skills、AI-Novel | 问题优先级、修订类别、避免 AI 抢作者决策 |
| Continuity | InkOS、graphify-novel、ani-book、ConStory 类 | 哪些确定性检查，哪些语义检查 |
| State Writeback | InkOS、AI-Novel、graphify-novel、ani-book | 正文发生了什么，何时进入 Canon |
| Controller / Author Decision Loop | creative-writing-skills Muse、InkOS、AI-Novel | 后台自动路由，重大决定作者确认 |

**达到可组合方案后停止搜索。**

---

# 四、次级 / 按真实问题触发的候选池

这些项目继续保留，但不占用当前主线注意力。只有相关能力出现真实缺口时再复查。

## NovelClaw

价值：dynamic-memory-first 长篇协作、章节规划、RAG / 记忆、一致性。

触发条件：Phase E Canon / Memory 候选比较仍缺成熟方案，或正式长篇暴露动态记忆问题。

## leenbj/novel-creator-skill

价值：文件级长期记忆、质量门、RAG、KG 回写、大纲锚点、断点恢复、Skill 形态。

触发条件：需要更轻量、可移植的文件工作流时复查。

## Ckokoski/AuthorAgent

价值：本地优先、分层记忆、consolidation、voice fingerprint、series bible。

触发条件：Memory / Voice / Series 真实问题出现时复查。

## story-skills

价值：简单标准化的创作项目结构与少量主要 Skill。

触发条件：Phase E 组合开始过度复杂时，用作“能否更简单”的对照。

## NousResearch/autonovel

价值：foundation → draft → review → revision 的自动迭代闭环、canon、voice fingerprint、reader panel。

触发条件：Phase F 创作沙盒需要完整自动迭代对照时复查。

## Long-Novel-GPT / StoryWriter / DOC / GOAT 等层级规划类

价值：多级规划、上下文选择、长篇生成研究。

触发条件：现有 Planner 候选在长篇层级规划上暴露真实不足时复查。

## ConStory 类一致性项目 / Benchmark

价值：人物、事实、叙事风格、时间/剧情、世界规则等长篇一致性错误分类。

触发条件：Phase E Continuity 需要明确错误 taxonomy 或 Phase F 暴露连续性问题时复查。

## BookNLP / 书籍级机械抽取工具

价值：实体归一、人物、引语说话者、事件等机械抽取。

触发条件：需要降低 LLM 在机械信息提取上的成本，且语言适配可行时复查。

---

# 五、历史 / 低优先级参考

以下不等于“差”，只是当前没有足够独特增量，或者已有更合适核心参照覆盖。

- `YILING0013/AI_NovelGenerator`：较早期完整生成流程参考；
- `t59688/arboris-novel`：作者辅助 / UI / 工作台体验参考；
- `PenglongHuang/chinese-novelist-skill`：与当前中文长篇核心候选重叠较多；
- `lornshrimp/Lorn.NovelWriteSkills`：能力重叠较高；
- `HZ-KMNO/web-novel-writing-guidance-skill`：思路接近，但当前核心参照已覆盖主要方向；
- `modoojunko/awesome-novel-skill`：工作流完整，但与核心池高度重叠；
- 各类只提供“多维打分 / 总分 9.x”的小说评估 Skill：不作为核心质量判断依据。

保留它们只是为了未来查历史，不再默认消耗 Benchmark 成本。

---

# 六、证据状态怎么写，避免再次误解

今后每个项目只用以下几种状态，不再用“参赛/淘汰”主导思路：

- **整体运行验证**：原项目按其真实工作流实际运行过；
- **局部机制实测**：只测试了其中明确一小部分；
- **方法级审查 / 已吸收原则**：认真阅读并采用了其方法，但没有声称整个工具已运行；
- **架构参照**：只用于工程设计比较；
- **按需候选**：真实问题出现时再复查。

禁止写法：

> “某个项目某个机制没参加 B02，所以这个项目失败。”

正确写法：

> “当前只验证到哪一层；没有验证到的部分保持未知。”

---

# 七、G3 closeout 后的固定结论

1. `AI-Novel-Writing-Assistant` 升级为最重要的完整工作台横向参照之一，不再归入 B 级次要工程候选。
2. `oh-story` 不只借局部钩子/节奏规则，要完整理解其拆解资产回流创作的链。
3. `creative-writing-skills` 不只用于后期正文检查；Reader Sim / Writing Principles 已成为原著 Discovery 的方法来源。
4. `Apodictic` 不再只等“未来某个专项 Benchmark”；它是 Developmental Deep Dive 和作者判断能力的长期参照。
5. `InkOS` 是 Phase E Context Compiler / Author Decision Loop / Story State 的核心参照。
6. Retrieval 技术链已经在 G3 关闭；不继续为了技术完整度搜索/升级 Retrieval。
7. Phase E 的重点是**组合**上述成熟上游，不是再扩大项目池。
8. 如果组合方案开始需要大量自研规则，先回本表检查是否漏看成熟能力。

---

# 八、一句话路由

> **以后不是“这个 GitHub 项目要不要参赛”，而是“当前真实创作问题需要什么能力，哪个成熟上游已经做得好，我们最小借什么，剩下什么才值得自己做”。**
