# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G4｜创作上下文与作者决策最小闭环：ACTIVE / G4-A。**

当前只允许完成/复核 G4-A 最小合同。未获用户明确确认，不自动进入 G4-B/C/D/E。

开始任务前先读：

1. `00_项目控制/README_目录使用说明.md`
2. `AGENTS.md`
3. `AI-write_长期开发手册.md`
4. `00_项目控制/当前工作索引.md`
5. `00_项目控制/项目推进记忆.md`
6. `00_项目控制/项目阶段门禁.md`
7. 当前专项协议/启动记录

并明确：当前 Gate、唯一目标、禁止范围、结束条件。

## 2. 作者交互原则

**作者控制 ≠ 作者审批。**

理想作者体验：

`AI 生成/修改正文 → 作者看正文并用自然语言说感觉 → Controller/Muse 自动路由相关能力 → 再修改 → 作者接受/拒绝 → 后台自动维护状态`

作者不应被要求：

- 手动挑十几个 Skill；
- 填复杂状态表；
- 理解内部 Schema；
- 审批每条机械 Story State 更新。

后台默认自动：Retrieval、Context 编译、Skill 路由、连续性检查、accepted text 的明确事实提取与机械结算。

必须作者确认：重大作品方向、人物核心动机/关系走向、重要生死、世界基本规则、卷级重规划，或真实冲突/歧义。

## 3. Story State authority

合法来源：

- `accepted_text:<ref>`：作者已接受正文中明确成立的事实；
- `author_decision:<id>`：作者明确确认的重大创作决定；
- 必要 `manual_import:<source>`。

禁止：

- BKP Pattern 直接成为 Canon；
- AI candidate / future branch / Context Package 直接写 Canon；
- 把正文没有明确成立的解释当成机械状态结算。

若事实有歧义，标记候选或询问作者。

## 4. Borrow-first

核心长期参照：AI-Novel-Writing-Assistant、oh-story、creative-writing-skills、Apodictic、InkOS、NovelForge、graphify-novel、ani-book-skill。

规则：

- 先理解成熟项目完整逻辑，再借局部；
- 能借不自研；
- 不把多个上游 schema 机械合成超级 schema；
- AI-write 自研集中在协议、路由、胶水、BKP、中文长篇适配、作者控制和必要状态接口；
- 实际复制/修改保留来源、commit/tag、LICENSE、修改范围。

## 5. Benchmark / 能力地图

- 普通能力默认真实任务轻量验证；
- 只有长期核心规则 + 证据矛盾 + 固化错误代价高时才升级严格 Benchmark；
- 六区成熟作者能力地图用于检查漏项；
- C01–C20 只是技术路由；
- taxonomy 不得成为发现边界；
- 单书 Pattern 不直接升级成普遍写作规则。

知识成熟度：

`Evidence → Observation/Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

## 6. 原著蒸馏规则

原著是最高事实源。BookDistill 当前：

- 长篇运行 / 读者动力：oh-story + AI-Novel；
- Reader / Page Craft：creative-writing-skills；
- 必要 Developmental Deep Dive：Apodictic；
- BookDistill 总编辑收敛为 BKP。

允许跨句/跨场景/跨章节证据，永久允许“重要但暂时无法命名”。不因单个案例新增硬编码 taxonomy。

## 7. G4-A 专项边界

当前五类工件：

1. Author Intent；
2. Story State / Canon；
3. Creation Brief；
4. Context Package；
5. Decision Record / State Diff。

当前合同：`06_工作区/G4A_最小创作合同_v0.1.md`（内容 v0.1.1）。

State Diff 至少区分：

- `mechanical_settlement`：accepted text 的明确事实，可自动应用；
- `creative_change`：重大创作变化，需作者确认；
- `ambiguous_inference`：不得自动写回。

Context 依赖 revision 改变后必须 stale；旧 Diff 不得覆盖新 state_rev。

## 8. 当前禁止

- 自动进入 G4-B；
- 完整 Writer / Reader / Critic / Editor；
- 正式长篇做实验；
- UI / 独立客户端；
- 大型数据库 / KG / 向量库 / 多 Agent 平台；
- 为工程完整度升级 Retrieval；
- BKP 自动写 Canon；
- AI 自动替作者做重大创作决定；
- 把作者变成后台状态审批员；
- 顺手扩展到后续 Gate。

## 9. Git 安全

无明确授权禁止：

`reset / restore / clean / force push / rebase / merge`

未知本地 dirty / untracked 不清理、不覆盖，先汇报。

2026-08-12 `BookDistill/SKILL.md` 重复 commit 已定性为历史噪音，不建立清理任务。

## 10. 文件生命周期

- `00_项目控制`：长期控制、门禁、记忆、能力地图、启动/收口记录；
- `06_工作区`：进行中实验、沙盒、协议草案；
- `05_Skills与自动化`：已形成可调用能力；
- `04_写作知识库`：经过跨作品/真实创作验证的高成熟知识；
- `02_原著蒸馏`：单书 BKP；
- `03_作品工程`：正式原创作品；
- `99_归档`：历史资料。

## 11. 防文档膨胀

长期手册和项目控制文件只保存稳定原则、当前边界和重大决策。

单次讨论、实验细节、临时方案优先放 `06_工作区` 或留在 Git 历史；不要每发现一个问题就新增长期章节。

## 12. 阶段切换

没有用户明确确认，不自动退出当前 Gate 或进入下一子阶段。

重大架构变化或 Gate closeout 时，同步检查长期手册、当前索引、项目记忆、门禁、AGENTS 和相关专项记录，并报告 commit SHA。