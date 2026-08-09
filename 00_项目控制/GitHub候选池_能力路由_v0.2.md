# GitHub 候选池｜能力路由 v0.2

> 日期：2026-08-09
> 状态：候选池清洗完成，供下一轮专项 Benchmark 选手冻结使用
> 原则：不选“项目总冠军”；只保留具有独特能力、明确工程价值或必要对照价值的上游。

## 一、当前正式保留池

### A 级｜核心能力候选：后续会直接进入专项 Benchmark

#### 1. worldwonderer/oh-story-claudecode

- 主要赛道：中文网文、追读、节奏、钩子、信息控制、对白、长篇拆文、正文工程、去 AI 味。
- 已有证据：B09 Round 01 正式参赛；在网文信息推进、钩子、读者期待等方面提供了独特能力来源。
- 后续：C08 对话、C10 信息控制、C11 连载留存、C14 中文自然度继续作为主要候选。
- 许可证：MIT。
- 当前处理：可直接 clone / 修改 / 适配；实际冻结时记录 commit。

#### 2. ExplosiveCoderflome/ani-book-skill

- 主要赛道：原著蒸馏、证据纪律、范围控制、fact/inference/hypothesis 分离、可恢复长篇 Markdown 工作流。
- 已有证据：B09 Round 01 正式参赛；其证据优先、置信度、反证和 coverage 控制值得保留。
- 后续：C19 原著蒸馏继续作为方法基线；不需要参加所有创作专项。
- 许可证：Apache-2.0。
- 当前处理：可直接 clone / 修改 / 适配。

#### 3. anotherpanacea-eng/apodictic

- 主要赛道：人物结构、情绪 craft、Scene/结构诊断、Reader experience、Reveal economy、Pacing、世界观整合、修订诊断。
- 独特价值：它不是单纯“代写 Skill”，而是以 development editor 为核心，强调诊断、结构和作者自己改；对 AI-write 的 C03/C04/C06/C09/C15/C18 很有价值。
- 后续：**B02 情绪传递首轮正式候选**；之后进入 B03/B04/B06 相关赛道。
- 许可证：CC BY-NC-SA 4.0。
- 当前处理：AI-write 已明确是私人、非商业工作台，因此允许本地复制、修改、Benchmark；保留来源/许可证标记。未来公开或商业化再统一审计。

#### 4. haowjy/creative-writing-skills

- 主要赛道：Character Sim、Reader Sim、Writer/Critic/Editor、Continuity、Style、知识库交接和 Muse 路由。
- 独特价值：能把“人物模拟”“读者模拟”“创作/评审/编辑”拆成不同角色，并有稳定的上下文交接思想。
- 后续：**B02 候选**；B01 人物声音、B05 对话、B07 Reader Sim/Character Sim 的主要上游。
- 许可证：Apache-2.0。
- 当前处理：可直接 clone / 修改 / 适配。

#### 5. iLearn-Lab/NovelClaw

- 主要赛道：dynamic-memory-first 长篇协作、章节规划、RAG/记忆、一致性。
- 独特价值：适合 C17 Canon/Memory，而不是人物情绪或 B09。
- 后续：B08 正式候选。
- 许可证：MIT。
- 当前处理：可直接 clone / 修改 / 适配。

#### 6. Narcooo/inkos

- 主要赛道：长篇真相文件、作者意图/current focus、上下文编译、plan→compose→write→audit→revise→state sync、结构化 delta 回写。
- 独特价值：输入治理、运行时 trace、真相文件和审计/修订闭环；适合研究未来 Controller 与长篇状态层。
- 后续：B08 / C20 架构专项候选；不进入 B02。
- 许可证：AGPL-3.0。
- 当前处理：当前私人本地研究可以 clone、运行和修改；保留来源。未来如分发或网络服务，再审计 AGPL 义务。

### B 级｜工程架构核心参考：不与轻量 Skill 正面对打，但会拆机制参赛

#### 7. RhythmicWave/NovelForge

- 主要赛道：JSON Schema 结构化生成、卡片、动态输出模型、上下文注入、知识图谱、状态回写。
- 独特价值：适合 C17/C20，特别是 Canon 数据结构、结构化生成和可控写回。
- 后续：B08 中拆“schema/canon/context/writeback”机制参与，而不是整套产品与 Prompt Skill 比输赢。
- 许可证：AGPL-3.0。
- 当前处理：私人研究可直接下载/修改；未来公开服务再审计。

#### 8. ExplosiveCoderflome/AI-Novel-Writing-Assistant

- 主要赛道：完整小说产品工作流、自动导演、规划→章节生产、RAG、角色/世界状态、任务恢复、模型路由、状态回灌。
- 独特价值：是 AI-write 未来完整工作台/运行时的工程参照，而不是某个文学技巧 Skill。
- 后续：B08 / C20 架构专项；拆出状态回灌、恢复、上下文选择、审批/生产边界做测试。
- 许可证：AGPL-3.0-only + 服务型商业用途单独授权说明。
- 当前处理：当前私人本地研究允许 clone/修改；未来如果 AI-write 对外做 SaaS/托管，必须重新审计或独立实现。

## 二、本轮新发现、值得加入观察池的项目

### 9. leenbj/novel-creator-skill

- 新发现价值：文件级长期记忆、五步质量门禁、RAG 两级检索、知识图谱回写、大纲锚点、断点恢复，且面向 Codex/Claude/OpenCode 等 Skill 形态。
- 适合：C17 Canon/Memory、C20 长篇工作流。
- 与现有候选关系：和 NovelClaw/InkOS/NovelForge 高度重叠，但因为它更接近“可移植 Skill + 文件状态”的形态，值得在 B08 前做一次代码级比较。
- 许可证：README 声明 MIT；本轮通过 GitHub 内容接口未找到根 `LICENSE` 文件，因此**冻结前必须再次核实许可证文件/仓库授权状态**。在核实前可研究公开结构，不先复制核心代码进 AI-write。
- 当前级别：`观察 → B08 前决定是否升级为正式候选`。

### 10. Ckokoski/AuthorAgent

- 新发现价值：本地优先、完整书籍流水线、CORE/ARCHIVAL/RECALL 分层记忆、睡眠式 consolidation、风格指纹、series bible。
- 适合：C17 Memory、C14 Voice、C20 本地工作台架构。
- 许可证：MIT，已核实根 LICENSE。
- 与现有候选关系：和 NovelClaw/InkOS 有重叠，但分层记忆设计足够独立，可作为 B08 的补充架构候选。
- 当前级别：`观察/架构候选`，不进入下一轮 B02。

### 11. NousResearch/autonovel

- 新发现价值：从 foundation→draft→review→revision 的自动迭代循环；有 canon、voice fingerprint、reader_panel、review/revision 脚本，并真实跑过整本书生产流程。
- 适合：C01、C12、C18、C20 的“自动迭代/评审闭环”研究。
- 风险：本轮检查没有找到根 LICENSE 文件。公开 GitHub 不等于拥有复制/改造授权；没有明确许可证时默认版权仍在作者。
- 当前处理：**只做架构/行为参考，不复制代码或 Prompt 进入 AI-write 核心**，除非后续许可证被明确。

## 三、降级为观察/历史基线，不再消耗近期 Benchmark 成本

### MaoXiaoYuZ/Long-Novel-GPT

- 有价值点：自上而下大纲→章节→正文、RAG 检索相关正文/纲要、修改正文同时同步剧情纲要。
- 原因：这些核心能力目前已有 NovelClaw/InkOS/NovelForge/AI-Novel-Writing-Assistant 等更活跃或更可拆分候选覆盖。
- 许可证：本轮未在根目录确认 LICENSE 文件。
- 处理：保留历史架构参考；不作为近期正式参赛者。

### YILING0013/AI_NovelGenerator

- 定位：较早期完整生成流程基线。
- 处理：历史参考，不进入近期能力赛道。

### t59688/arboris-novel

- 定位：作者辅助/UI/工作台体验参考。
- 处理：产品体验观察，不作为当前文学能力 Benchmark 主参赛者。

## 四、退出正式候选池

以下项目不等于“差”，只是目前没有足够独特增量，或质量/许可证/重复度不值得继续占用 Benchmark 成本：

- `PenglongHuang/chinese-novelist-skill`：流程完整但模板化倾向较强，与 oh-story/其他中文长篇 Skill 重叠；曾存在许可证核实问题。
- `lornshrimp/Lorn.NovelWriteSkills`：能力重叠较高，且存在伪精确/自评分倾向；许可证仍需核实。
- `HZ-KMNO/web-novel-writing-guidance-skill`：思路与当前 AI-write 很接近，但现阶段社区/实证信号弱，且大量能力已被核心候选覆盖。
- `modoojunko/awesome-novel-skill`：工作流完整但与 oh-story、creative-writing-skills、长篇工程候选高度重叠；先不扩大池子。
- `wgwtest/novel-writing`、`howells/fiction` 等小型新 Skill：可继续观察，但当前没有证明其提供核心池尚未覆盖的独特机制。
- 各类“多维打分/总分 9.x”小说评估 Skill：不进入正式池，避免把主观创作质量伪装成单一分数。

## 五、方法论参考，不作为小说能力参赛者

### anthropics/skills

- 用途：Skill 设计、progressive disclosure、真实任务评测、with-skill vs baseline、迭代方法。
- 不参加“谁更会写小说”的比赛。
- 使用时逐文件检查许可证，不假定整个仓库所有内容许可证完全一致。

## 六、候选池 → 能力路由

| 能力赛道 | 第一候选 | 第二/补充候选 | 暂不参与 |
|---|---|---|---|
| C03 人物心理/自主性 | Apodictic | creative-writing-skills Character Sim | 大型工作台项目 |
| C04 情绪传递 B02 | Apodictic | creative-writing-skills；oh-story 作为中文正文对照 | Canon/Memory 项目 |
| C08 对话/潜台词 | creative-writing-skills | oh-story、Apodictic、B09-K2 | NovelForge/InkOS |
| C09 Scene Turn | Apodictic | oh-story、B09-K1 | Memory 项目 |
| C10 悬念/信息 | oh-story | B09-K4；K3 轻规则 | 暂不新开主赛道 |
| C11 连载留存 | oh-story | 网文蒸馏结果 | 文学编辑型项目 |
| C12 Reader Sim | creative-writing-skills | autonovel reader_panel（仅参考，许可证未明） | 普通“评分器” |
| C14 中文自然度/Voice | oh-story | creative-writing-skills Style；后续作者语料 | 单纯禁词表 |
| C17 Canon/Memory | NovelClaw | InkOS、NovelForge、AI-Novel-Writing-Assistant；novel-creator-skill/AuthorAgent 观察 | 情绪/文学 Skill |
| C18 修订诊断 | Apodictic | creative-writing-skills Critic/Editor、oh-story review | 单纯自动重写器 |
| C19 原著蒸馏 | ani-book | oh-story、AI-write Candidate、D0 | B09 当前暂停 |
| C20 Controller/Context | AI-write 自身 | InkOS、NovelForge、AI-Novel-Writing-Assistant、AuthorAgent | 现在不先组装 |

## 七、下一轮 B02 的候选冻结建议

B02 不再沿用旧的“Baseline + oh-story + 自研情绪 Prompt”三方结构。建议更新为：

1. `D0`：同模型，无小说 Skill strong baseline；
2. `A`：Apodictic 情绪/人物相关机制适配；
3. `B`：creative-writing-skills Character Sim / craft 相关机制适配；
4. `C`：oh-story 中文正文/情绪相关方法；
5. `D`：AI-write Candidate —— **必须在 A/B/C 独立方案明确后再设计，不能提前把三家优点全抄进去造成不公平。**

首轮至少 3 个不同性质的情绪任务：

- 爱情：吃醋但不承认；
- 权力：下属受辱但不能发作；
- 丧失：亲人死亡后异常冷静，不能直接贴“悲痛”标签。

核心作者评审保持普通语言：

- 哪一版人物最像活人？
- 哪一版情绪最能自然传到读者？
- 哪一版最自然、最少 AI/模板感？
- 哪个具体设计值得留下？

Controller 再检查机制增量、动作模板率、人物自主性、关系变化、成本和副作用。

## 八、下载/冻结策略

下一步不把整个候选池全部塞进 AI-write 核心。由本地 Agent 在专项启动前建立“上游冻结候选区”，每个实际下载项目记录：

`repo URL | frozen commit/tag | LICENSE | 下载日期 | 使用能力 | 复制/修改范围 | 是否 restricted-source`

处理原则：

- MIT / Apache-2.0：可积极复制、修改、汉化、拆解并固化为本地 Skill。
- CC BY-NC-SA / AGPL：当前私人用途不自动排除；可本地研究、修改、Benchmark，保持来源标记；未来公开/商业化时再审计。
- 无明确许可证：只研究思想和公开行为，不直接复制代码/Prompt 进入核心。

GitHub 是上游零件库；最终生产运行应尽量使用 AI-write 自己的本地 Skill，而不是每次写作联网依赖上游项目。
