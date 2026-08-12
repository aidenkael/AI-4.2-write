# AI-write Agent 长期规则

本文件面向进入仓库工作的 Codex / Agent。项目事实与目录规则仍以 `00_项目控制/README_目录使用说明.md` 及对应 STATUS/协议为准；根目录 `AI-write_长期开发手册.md` 记录长期架构、开发路线和防战略漂移原则；本文件保存跨任务执行约束。

## 1. 项目定位

AI-write 当前是作者个人、私人使用的小说写作工作台。长期目标是辅助不同题材、不同风格的真实长篇创作，而不是只服务某一本书或某一种网文模板。

工作台应让作者主要面对真实创作：参考/研究、构思、规划、写、审阅、修改。Book Knowledge、Canon、Retrieval、Context Compiler、Writer、Critic、Continuity、Controller 等属于后台能力，不应要求作者手动操作一堆 Skill。

当前阶段边界：**G3 已于 2026-08-12 正式关闭（`G3_RETRIEVAL_VALIDATED / CLOSED`）；下一长期方向是 Phase E｜创作核心后台，但尚未自动建立下一 Gate。** 未经用户确认下一 Gate 的名称、目标、退出条件和禁止范围，不得自动开始 Phase E 实质开发。

## 2. 开源上游使用原则

**Borrow-first，不重复造轮子。** 技术筛选阶段不要因为许可证类型自动排除高价值开源项目。只要适合当前私人研究，可积极：

- clone / 下载上游项目；
- 研究并复用其成熟代码、Prompt、Skill、规则、schema 与工作流；
- 汉化、修改、删减、组合、重构；
- 对真正进入 AI-write 的部分保留来源与 provenance；
- 后续优先收敛为本地稳定能力，不要求运行时每次访问 GitHub 或原作者服务。

AI-write 自主研发应尽量集中在：协议、路由、胶水、Book Knowledge Package、BookProfile 路由逻辑、中文长篇适配、作者控制和必要的状态接口。Writer、Critic、Reader、Planning、Canon、Memory、Continuity、RAG/KG 等若已有成熟实现，先比较/借鉴再决定是否自研。

当前核心长期参照优先看：AI-Novel-Writing-Assistant、oh-story、creative-writing-skills、Apodictic、InkOS、NovelForge、graphify-novel、ani-book-skill。详细分工见 `00_项目控制/GitHub候选池_能力路由_v0.2.md`。

## 3. 来源与许可证记录

对任何实际复制或修改的上游，至少保留：

`来源仓库 | 上游 commit/tag | LICENSE | 复制/修改范围`

处理原则：

- MIT / Apache-2.0：当前可直接下载、修改、适配、融合，按许可证保留必要声明。
- CC BY-NC-SA 等非商业/ShareAlike 来源：当前私人、非商业研究和本地改造可以纳入候选；必须保留来源与许可证标记。未来若公开、商业化或分发，再重新审核。
- AGPL 等强 copyleft：当前可本地下载、运行、修改、Benchmark；保留来源与许可证，未来若分发软件或提供网络服务，再专门审核相应义务。
- 许可证不明：可以研究思想和公开行为，但在未核实前不要直接复制其受版权保护的代码/Prompt 进入核心。

许可证是 provenance / 未来分发审计问题，不是当前技术价值排序的主要依据。

## 4. Benchmark、吸收与知识等级

- 不按 GitHub 项目选“总冠军”，按真实能力需求路由。
- 始终保留 strong baseline，防止把模型本来就会的能力误认为 Skill 增益。
- 普通能力默认轻量验证：筛选 → 最小真实任务 → 作者判断 → 吸收/保留/放弃。
- 只有高价值、证据矛盾、错误固化代价高时才升级严格 Benchmark。
- 作者主要判断实际小说问题与创作效果；内部术语、证据、许可证、能力归类由 Controller / Agent 处理。
- 候选池不再按“参赛/淘汰”主导；必须区分整体运行验证、局部机制实测、方法级审查/已吸收原则、架构参照、按需候选。

### 禁止把单书观察直接固化成写作定律

知识状态必须区分：

`Source Evidence → Observation / Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

例如一本书里的 Pattern 首先只是该作品的可追溯观察/假设；未经跨书与真实创作验证，不得写成 AI-write 的普遍写作规则。

`04_写作知识库` 不接收仅凭单本作品、高度总结或模型直觉产生的“正式规律”。

## 5. 原著蒸馏长期规则

当前 SourcePrepare + BookDistill v0.2.x + BKP v0.1 已完成 Phase C 技术验证，并由《一九八四》《三体》两个差异明显的真实样本跑通。BookDistill 的 evidence-first、来源 fingerprint、章节/行号校验、BookProfile、1～N Deep Dive、BKP Finalize 都属于可保留地基。

但“工具能跑、BKP 能生成、Retrieval 能检索”不等于“作品真正最值钱的创作智慧一定被充分发现”。2026-08-12 已完成方法级修正：BookDistill 不再被要求单枪匹马发现全部精华，而是作为总编辑收敛多视角直接原著观察。

默认 Discovery：

1. **长篇运行 / 读者动力镜头**：优先借 oh-story + AI-Novel-Writing-Assistant；
2. **Reader / Page Craft 镜头**：优先借 creative-writing-skills；
3. **必要时 Developmental Deep Dive**：优先借 Apodictic；
4. **BookDistill 总编辑**：回源核证、区分 Observation/Inference、去重、发现组合效果、补 Scope/Boundary/Counterevidence/Confidence、必要时再深挖，最终封装一个 BKP。

关键规则：

- 原著始终是最高事实源；重要观察能力必须能够直接读取原著，不能只吃上一层摘要；
- 允许一条 Observation 由跨句、跨场景、跨章节证据共同支撑；
- 永久允许“重要但暂时无法命名”的 Observation / Inference；
- Discovery 可以宽，最终 BKP 必须克制；
- 不因为单个案例新增硬编码 taxonomy；
- 不要求为了方法升级重跑《一九八四》《三体》；未来新书真实蒸馏时验证即可。

BookProfile 规则：

1. 不得在基础全书观察前裁掉未知维度；
2. Profile 负责分配后续蒸馏预算，不负责永久判定某维度“不值得学”；
3. 至少记录价值判断、证据量、置信度、反例/不确定性、是否需要专项深挖；
4. 必须允许“高价值全能型作品”在多个维度同时进入深挖；
5. 蒸馏次数不固定，只要求每次解决明确且有价值的问题。

当前仍禁止批量蒸馏几十本素材或冻结最终 BKP schema。后续批量化必须由真实创作与新书验证证明当前 Discovery / BKP 足够稳定后再决定。

## 6. 商业化边界

当前无需为尚未发生的商业化过度设计限制。只有未来公开发布、出售/授权、提供在线服务或大规模分发修改后的上游时，才触发统一许可证审计。

## 7. Git 同步与本地保护规则

以下规则优先级高于任何自动化同步逻辑：

1. **用户明确确认的意图是最终依据。** 本地工作树与远端发生未知差异时，任何一边都不得自动覆盖另一边；先 `fetch` + `compare`，再由用户/Controller 确认。
2. **用户本地删除 / 移动 / 改名不得自动 restore。** 如果用户已从磁盘删除某个 tracked 文件，Agent 不得因为 GitHub 上仍存在就 `git checkout`、`git restore` 或 `git reset` 把它取回。
3. **未知差异优先 `fetch` + `compare`。** 发现本地与远程不一致时，先 `git fetch origin` 再用 `git log` / `git diff` 对比，而不是直接 pull 覆盖。
4. **pull 前先确认工作树。** 确认当前 branch、未提交修改、stash 状态；如果工作树不干净，先报告风险，不得强行 pull。
5. **禁止未经授权执行：** `git reset --hard`、`git restore .`、`git checkout -- .`、`git clean -fd`、`git push --force` / force push、`git rebase`、`git merge`，以及任何批量 restore / clean / 历史重写。
6. **Local Only / untracked 不得为了整洁自动清理。**
7. **用户确认删除 tracked 文件时，通过正常 Git 删除并 commit。**
8. **重大目录调整必须：** 审计 → 清单 → 用户/Controller 确认 → 执行。
9. **Agent 临时指令与临时反馈默认不进入 `00_项目控制`。**
10. 2026-08-12 GitHub 连接器曾为 `BookDistill/SKILL.md` 产生多条同名重复 commit；最终内容正确。该历史噪音已记录在 `G3_收口记录_2026-08-12.md`，**不得以后自行开启“清理历史”任务。**

## 8. 文件生命周期规则

### `00_项目控制` — 项目级长期控制文件

准入：项目总体说明、长期规则、能力地图、门禁、项目记忆、权威索引、阶段 closeout 记录等。单轮实验/临时 Agent 文件默认不放这里。

### `06_工作区` — 进行中的工作

当前调研、Benchmark、实验材料、中间分析、未验证机制等。结束后按价值提升或归档。

### `05_Skills与自动化` — 已形成可调用能力

经过验证的 Skill、脚本、Agent/自动化和运行时组件。

### `04_写作知识库` — 已验证的跨作品知识

只存经过足够验证、可跨作品复用的知识；单书 Observation/Pattern 默认留在对应 BKP，不自动升级到这里。

### `99_归档` — 历史资料

已结束的 Benchmark、被新版替代但仍需追溯的文件、一次性有参考价值的报告。更新长期权威文件前，如果旧版本仍有重要历史细节且新版会大幅收束，可先原样归档再改当前版。

## 9. 项目阶段门禁与防跑偏规则

任何 Agent 开始实质任务前必须按顺序读取：

1. `00_项目控制/README_目录使用说明.md`
2. `AGENTS.md`
3. `AI-write_长期开发手册.md`
4. `00_项目控制/当前工作索引.md`
5. `00_项目控制/项目推进记忆.md`
6. `00_项目控制/项目阶段门禁.md`
7. 本次专项 STATUS / 协议（如有）

长期约束：

1. 当前 Gate 未完成且未经用户明确确认，不得自行进入下一阶段。
2. **当前没有自动建立下一 Gate。** G3 CLOSED 后，只允许在用户确认前做 Phase E 的小型 Borrow-first 组合方案，不得自动进入大规模开发。
3. 单次任务只推进一个明确目标；发现额外问题可以记录，不得“顺手扩展”。
4. 候选池出现过某项目，不等于已整体运行验证；必须区分证据层级。
5. 新 Benchmark、重大目录变化、批量处理、新架构建设、跨门禁动作均需要用户明确授权。
6. 聊天建议与长期手册/当前索引/项目记忆/门禁或用户最新决定冲突时，先停止并对齐。
7. 不得为了“赶 Gate”跳过已确认的成熟方案复查、关键协议设计或作者确认。

## 10. 工作台架构规则

- 成熟作者能力战略上用六个大区检查是否漏项；C01–C20 只是技术路由地图，不是一一对应的作者 Skill 清单。
- 永久允许“重要，但目前无法命名”，taxonomy 不得成为发现边界。
- Skill、Agent、角色、脚本、知识库、数据库、服务必须分层，不要为了结构整齐全部做成 Skill。
- 后台能力应与界面解耦；近期优先 Agent + Markdown/Git/Obsidian，是否做插件、本地 Web 或独立客户端由真实使用痛点决定。
- 当前不为“面子”提前开发完整 UI；先做稳定的“里子”。
- 正式小说不作为未经验证工具的实验主线；新能力优先在沙盒/shadow copy 中测试。
- Retrieval 只负责搬运“小而相关”的知识；Cross-book Synthesis 属于未来 Context Compiler / Muse / Planner，不得把 Retrieval 做成“超级大脑”。
- Author Decision Loop 的目标是 AI 给方案/证据/风险/推演，作者掌握重大创作取舍，确认后再写回计划/Canon/Story State。

## 11. 阶段收口 Definition of Done

完成一个 Gate 或确认重大架构变化时，Agent 必须同步检查并在需要时更新：

1. 根目录 `AI-write_长期开发手册.md`；
2. `00_项目控制/当前工作索引.md`；
3. `00_项目控制/项目推进记忆.md`；
4. `00_项目控制/项目阶段门禁.md`；
5. `AGENTS.md`（仅长期规则变化时）；
6. `00_项目控制/GitHub候选池_能力路由_v0.2.md` / 能力地图（若上游定位或能力路由发生变化）；
7. 相关专项 STATUS / provenance / closeout 记录。

然后 commit，并报告改动、理由、commit SHA、当前 Gate。**没有用户明确确认，不自动进入下一 Gate。**
