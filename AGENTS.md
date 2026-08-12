# AI-write Agent 长期规则

本文件面向进入仓库工作的 Codex / Agent。目录和事实以 `00_项目控制/README_目录使用说明.md`、当前 Gate、长期开发手册和专项协议为准；本文件保存跨任务执行约束。

## 1. 项目定位与当前阶段

AI-write 是作者个人、私人使用的小说写作工作台，长期目标是辅助不同题材、不同风格真实长篇创作，而不是只服务某一本书或某一种网文模板。

作者主要面对：`参考/研究 → 构思 → 规划 → 写 → 审阅 → 修改`。

Book Knowledge、Canon/Story State、Retrieval、Context Compiler、Planner、Writer、Reader/Critic/Editor、Continuity、State Writeback、Controller 等属于后台能力，不应要求作者手动操作一堆 Skill。

**当前正式 Gate：G4｜创作上下文与作者决策最小闭环（ACTIVE / G4-A）。**  
G3 已 `G3_RETRIEVAL_VALIDATED / CLOSED`。  
G4 启动记录：`00_项目控制/G4_启动记录_2026-08-12.md`。

当前只允许推进 **G4-A｜成熟上游压缩成最小合同**。不得自动进入 G4-B/C/D/E，也不得把 Phase E 一次做成完整创作系统。

## 2. Borrow-first

**Borrow-first，不重复造轮子。**

当前核心长期参照：

- AI-Novel-Writing-Assistant；
- oh-story；
- creative-writing-skills；
- Apodictic；
- InkOS；
- NovelForge；
- graphify-novel；
- ani-book-skill。

详细分工见 `00_项目控制/GitHub候选池_能力路由_v0.2.md`。

使用原则：

- 先理解成熟项目完整工作逻辑，再借局部；
- 能直接借就不自研；
- 项目整体很重不代表其中成熟能力不能拆；
- 不把多个上游 schema 机械合成超级 schema；
- AI-write 自研尽量集中在协议、路由、胶水、BKP、中文长篇适配、作者控制和必要状态接口；
- 当前私人研究阶段许可证不作为技术淘汰条件，但实际复制/修改必须记录来源、commit/tag、LICENSE、修改范围；未来公开/商用/服务化/分发再审计。

## 3. Benchmark 与知识成熟度

- 不按 GitHub 项目选“总冠军”，按真实能力需求路由；
- 普通能力默认轻量验证；
- 只有长期核心规则、证据矛盾、错误固化代价高时才升级严格 Benchmark；
- B02/B09 方法学经验保留，不主动重启大型研究流程；
- 作者主要判断实际小说效果，内部术语和证据分级由 Controller / Agent 处理。

知识状态：

`Source Evidence → Observation / Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

单书 Pattern 未经跨书和真实创作验证，不得写成普遍写作定律。

## 4. 原著蒸馏长期规则

SourcePrepare + BookDistill v0.2.x + BKP v0.1 已完成 Phase C 技术验证；《一九八四》《三体》两个差异明显的真实样本跑通。

BookDistill 当前正式方法：

```text
原著（最高事实源）
├─ 长篇运行 / 读者动力：oh-story + AI-Novel
├─ Reader / Page Craft：creative-writing-skills
├─ 必要 Developmental Deep Dive：Apodictic
└─ BookDistill 总编辑：回源核证 → 去重 → 组合效果 → Scope/Boundary/Counterevidence/Confidence → BKP
```

规则：

- 重要观察能力必须能直接读原著；
- BookProfile 是导航/预算工具，不是过滤器；
- 允许跨句、跨场景、跨章节组合证据；
- 永久允许“重要但暂时无法命名”；
- Discovery 可以宽，最终 BKP 必须克制；
- 不因单个案例新增硬编码 taxonomy；
- 不要求为了方法升级重跑旧书；
- 当前仍禁止批量蒸馏几十本参考书或冻结最终 BKP schema。

## 5. BKP 与 Canon 必须严格分离

- **BKP / Book Knowledge**：参考作品知识；
- **Canon / Story State**：原创作品权威事实与当前状态。

参考知识不能自动写入 Canon；原创事实不能写进参考书知识。

向量、图谱、索引、Context Package 等默认是可重建派生层，不应取代权威状态。

## 6. G4 专项规则

G4 只验证五种概念工件：

1. Author Intent；
2. Story State / Canon；
3. Creation Brief；
4. Context Package；
5. Decision Record / State Diff。

当前 G4-A 只做：

- 最小字段；
- 权威 vs 派生边界；
- 谁可建议、谁可写入；
- 哪些写入必须作者确认；
- provenance / trace / state diff 最小关系；
- 哪些上游字段不值得搬入 AI-write。

G4 当前严禁：

- 完整 Writer；
- 完整 Reader Sim / Critic / Editor；
- 正式长篇；
- `03_作品工程` 正式作品作为工具试验品；
- UI / Obsidian 插件 / 独立客户端；
- 大型数据库 / KG / 向量库；
- KnowledgeRetrieve 升级；
- 大型多 Agent 平台；
- 超级 Canon schema；
- BKP 自动写入 Canon；
- 作者确认前修改重大 Story State；
- Controller 自动替作者决定重大方向；
- 顺手做后续 Gate 功能。

完整边界以 `项目阶段门禁.md` 与 `G4_启动记录_2026-08-12.md` 为准。

## 7. Author Decision Loop

长期目标：

`AI 给方案 / Evidence / 风险 / 推演 → 作者选择 / 修改 / 拒绝 → 作者确认后才更新计划 / Canon / Story State。`

作者偏离旧计划时，系统应先说明影响，不得先偷偷改状态。

AI-write 的目标是提高作者判断力，而不是把作者从重大创作决策里删除。

## 8. Git 同步与本地保护

以下规则优先级高于任何自动化同步逻辑：

1. 用户最新明确确认的意图是最终依据；未知差异先 fetch + compare；
2. 用户本地删除/移动/改名不得自动 restore；
3. pull 前确认 branch、dirty、stash；工作树不干净先报告；
4. **禁止未经授权执行：** `git reset --hard`、`git restore .`、`git checkout -- .`、`git clean -fd`、force push、`git rebase`、`git merge` 或其他历史重写/批量清理；
5. Local Only / untracked 不得为了整洁自动清理；
6. 重大目录调整必须：审计 → 清单 → 用户/Controller 确认 → 执行；
7. Agent 临时指令与临时反馈默认不进入 `00_项目控制`；
8. 2026-08-12 `BookDistill/SKILL.md` 的多条同名重复 commit 已定性为历史噪音，最终内容正确，**不得以后自行开启“清理历史”任务。**

## 9. 文件生命周期

- `00_项目控制`：项目级长期控制、门禁、记忆、能力地图、上游路由、启动/closeout 记录；
- `06_工作区`：进行中调研、实验、沙盒、中间分析、未验证机制；
- `05_Skills与自动化`：已形成可调用能力；
- `04_写作知识库`：经过足够跨作品与创作验证的高成熟度知识；
- `99_归档`：被替代但仍需追溯的历史资料；
- `01_原始素材`：Local Only；
- `02_原著蒸馏`：单书 BKP；
- `03_作品工程`：正式原创作品。

## 10. 项目阶段门禁与防跑偏

任何 Agent 开始实质任务前按顺序读取：

1. `00_项目控制/README_目录使用说明.md`
2. `AGENTS.md`
3. `AI-write_长期开发手册.md`
4. `00_项目控制/当前工作索引.md`
5. `00_项目控制/项目推进记忆.md`
6. `00_项目控制/项目阶段门禁.md`
7. 本次专项 STATUS / 启动记录 / 协议

长期约束：

- 当前 Gate 未完成且未经用户明确确认，不得自行退出或进入下一阶段；
- 单次任务只推进当前子阶段一个明确目标；
- 候选池出现过某项目不等于已整体验证；
- 新 Benchmark、重大目录变化、批量处理、新架构建设、跨 Gate 动作需用户明确授权；
- 聊天建议与长期文件冲突时先停止并对齐；
- 不为“赶 Gate”跳过成熟方案复查、关键协议或作者确认。

## 11. 工作台架构规则

- 成熟作者战略上用六区检查漏项；C01–C20 只做技术路由；
- taxonomy 不得成为发现边界；
- Skill、Agent、角色、脚本、知识库、数据库、服务分层；
- 后台与界面解耦；
- 正式小说不作为未经验证工具的实验主线；
- Retrieval 只搬运小而相关知识；Cross-book Synthesis 属于 Context Compiler / Muse / Planner；
- Context Package 是派生层，不得成为 Canon；
- 权威状态必须可在新会话中独立恢复，不依赖聊天记忆。

## 12. 阶段收口 Definition of Done

完成 Gate 或重大架构变化时，必须同步检查：

1. `AI-write_长期开发手册.md`；
2. `00_项目控制/当前工作索引.md`；
3. `00_项目控制/项目推进记忆.md`；
4. `00_项目控制/项目阶段门禁.md`；
5. `AGENTS.md`；
6. 候选池 / 能力地图（若定位变化）；
7. 相关 STATUS / provenance / 启动或 closeout 记录。

然后 commit，报告改动、理由、SHA、当前 Gate，并明确已证明/未证明。**没有用户明确确认，不自动退出当前 Gate。**