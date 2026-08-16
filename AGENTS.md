# AI-Write Agent 长期规则

> 面向进入仓库工作的 Agent。目标是让后台复杂度服务作者，作者不管理系统。

## 当前阶段

**CURRENT_PHASE = REAL_WRITING_USAGE**

工作台已从开发验证期进入真实使用期。主目标是辅助作者进行长篇小说创作。

## 核心目标

让后台复杂度服务作者。作者不管理 Prompt / Agent / Skill / Schema / Context ID。

## 目录 authority

| 目录 | 职责 | Authority |
|---|---|---|
| 01_原始素材 | 未经 AI 加工的原始来源 + 素材资产.json（canonical ledger） | 原始文件真相 + canonical registry |
| 02_素材知识库 | 参考作品结构化知识（BKP） | 参考知识 |
| 03_作品工程 | 原创小说作品 | **原创最高 authority** |
| 04_写作知识库 | 经多作品验证的长期写作知识 | 跨作品经验 |
| 05_Skills与自动化 | 工作台可调用能力 | capability |
| 06_工作区 | 临时运行空间 | derivative/temp |

## 创作 authority 顺序

1. 作者当前明确决定
2. 作者接受正文 / production Story State
3. 当前有效规划（active planning）
4. 参考知识 BKP / 04 knowledge

**BKP 不得成为原创 Canon。** 未接受文本不得进入 production 正文/State。
Context/Brief/recent prose 是 derivative，不得成为事实 authority。

## 正式能力状态

| 子系统 | 状态 |
|---|---|
| MaterialIntake | CANONICAL_CATALOG_AVAILABLE + INTAKE_AND_WRITEBACK_AVAILABLE（素材资产.json = 唯一 canonical 真源；CSV/MD derived） |
| SourcePrepare | AVAILABLE（canonical ledger consumer；index_builder 已退役） |
| BookDistill | AVAILABLE / FROZEN |
| KnowledgeRetrieve | AVAILABLE / FROZEN |
| StoryDesign | CLOSED / FROZEN |
| StoryPlan | CLOSED / FROZEN |
| ContextCompiler | CONSUMER_DRIVEN_FREEZE |
| StoryWrite primitives | KEEP_AND_FREEZE |
| Mechanical settlement assist | KEEP_AND_FREEZE |
| AUTHOR_FACING_ONE_SENTENCE_ENTRY | NOT_YET_PROVEN |
| WRITER_PLATFORM_REQUIRED | NO |

## 方法链

`SourcePrepare → BookProfile → 多视角 Discovery → 按需 Deep Dive → BookDistill 收敛 → BKP → KnowledgeRetrieve`

## BKP 边界

BKP 长期保存作品身份、作品地图、BookProfile、Observation、Inference、Pattern、Deep Dive 和可追溯 Evidence。

单书 BKP 不自动升级为普遍写作规则。BKP 策略：`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`。

## Context 规则

- 仅显式选择，空 selection 不 fallback 整包
- State selection 必须 explicit
- Context Package 是可重建派生层，不是 authority

## 开发原则

`CAPABILITY_FIRST_CONSUMER_DRIVEN`：冻结子系统没有真实 consumer blocker 不重开。

开发决策规则：只有同时满足（1）真实使用暴露问题；（2）问题重复或严重；（3）现有能力不能低成本解决；（4）新代码能明显降低长期负担，才允许建议新 runtime。否则 DO_NOT_BUILD。

窄口径：`THIN_ORCHESTRATION_BUILD_ALLOWED`——只允许复用现有合同的薄操作层；不代表 Writer platform 获批。

## Borrow-first

`真实问题 → 查成熟上游 → 能借就借 → 最小适配 → 真实运行`

当前优先参照：
- oh-story / AI-Novel-Writing-Assistant：长篇运行、拆文
- creative-writing-skills：Reader / Craft
- Apodictic：Developmental Editing
- ani-book-skill：evidence-first、权威工件

## 当前禁止

- 未获得作者明确 acceptance / decision 时，不得修改 production 正文或 Story State
- 作者明确接受正文或作出创作决定后，允许按照现有 authority / writeback 合同更新
- AI 自己的草稿、推测、candidate、Context、Brief 不得自动升级为 production authority
- 不批量蒸馏新书
- 不升级 Retrieval/RAG/KG
- 不实现完整 Writer/Reader/Editor/Controller/UI 平台
- 不为了测试主动制造小说
- 不为一次任务新造长期 Skill

## Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

临时 worktree 默认进入系统 TEMP，不在 E:\ 根留下 AI-Write-*。任务完成后删除 worktree。

## Post-Action Writeback（Phase 2B2 / 2B2.1）

三个工作台动作完成后**自动**执行「更新长期 tracked 状态 → 最小验证 → git fetch → 安全 commit → 普通 fast-forward push」，
作者无需重复要求“记得更新清单/索引/GitHub”：

| 动作 | 完成条件 | allowlist（本次动作最小必要面，非 subsystem 整目录授权） |
|---|---|---|
| MATERIAL_INTAKE | intake apply 成功（完整事务） | 三份 material state files：`01_原始素材/素材资产.json` + `素材清单.csv` + `素材总索引.md` |
| SOURCE_PREPARE | formal 结果（PASS/REVIEW/FAIL）且 metadata 完整（refresh 成功）且无 runtime ERROR | 同上（SP 输出在 `06_工作区`，Local Only） |
| BOOK_DISTILL | BKP FINALIZED + 全部验证通过（settlement，每作品一次） | 当前 book_id 的单一 distillation subtree（`02_素材知识库/<book_id>_<书名>/`）+ 三份 material state files |

规则：

- 实现统一收敛在 `MaterialIntake/post_action.py`（PRECHECK + SAFE_COMMIT_PUSH）：
  绝不 merge / rebase / force / reset / restore / clean / pull；远端前进 → STOP 保留现场；
  allowlist 外任何 tracked 变更 → STOP；无变化 → 不造空 commit。
- **MATERIAL_INTAKE 是完整事务**（ROLLBACK_ON_FAILURE=TRUE）：动作前只读 catalog health check
  （失败 → STOP_BEFORE_MOVE）；修改 canonical 前保存三份 metadata byte snapshot；
  move / ledger / refresh 任一失败 → 按 journal 逆序恢复文件 + 恢复三份 metadata + 清理新建空目录
  （不依赖 git restore）；exact duplicate 延迟到 settlement 成功后删除。
- **Git sync 失败不回滚业务动作**：catalog settlement 已完整成功后，post_action 因
  REMOTE_ADVANCED / UNEXPECTED_DIFF / push race 停止 → 本地 durable action 已完成，保留现场人工处理 Git。
- 原始素材（*.epub/*.txt/*.pdf/*.mobi/*.azw3/*.zip）、`06_工作区/SourcePrepare/`、`collection_manifest.json`
  任何 action 绝不 staging（第二道过滤）。
- 测试/调试使用 `--no-git-sync` 或 tmp git repo；真实 sync 需 worktree clean + HEAD==origin/main；
  SP production 默认在转换前执行 `post_action.precheck`，失败立即 STOP。
- **不泛化到原创 Canon**：AI 草稿 / candidate / Brief / Context / Story State 绝不自动进 Git，
  原创作品只按作者显式 acceptance / decision 与既有合同管理。

## NEXT

真实 author acceptance：
- 作者接受正文 → accepted_text
- 进入 production Story State
- 生成 next Context

不以 Benchmark / Gate / Phase 编号驱动。以真实创作产出驱动。
