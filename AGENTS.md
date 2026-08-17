# AI-Write Agent 长期规则

> 面向进入仓库工作的 Agent。目标是让后台复杂度服务作者，作者不管理系统。

## 当前阶段

**CURRENT_PHASE = REAL_WRITING_USAGE**

工作台已从开发验证期进入真实使用期。主目标是辅助作者进行长篇小说创作。

## 核心目标

让后台复杂度服务作者。作者不管理 Prompt / Agent / Skill / Schema / Context ID。

作者应使用自然语言表达“新建/继续/切换作品、构思、规划、写、修改、确认方向、接受正文”；Agent 负责识别后台能力。不要要求作者记 StoryDesign / StoryPlan / ContextCompiler / KnowledgeRetrieve / StoryWrite 名称，也不要要求作者维护一组 Skill Prompt 模板。

## 作者侧产品规则

- 后台按成熟作者标准工作，前台按普通新手可理解的方式交流。
- 作者操作作品，不操作 Agent、模型或 Skill。
- 高频明确操作可以按钮化；模糊和创造性需求保留自然语言。
- candidate / draft / proposal 默认不是 authority，作者明确采用后才能正式写入。
- 当前 UI 设计 ACTIVE 但 NOT FROZEN，不能把讨论中的页面结构当最终规范。

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

## 多作品长期规则

**KNOWLEDGE_SHARED_AUTHORITY_ISOLATED**。

- `02_素材知识库` 与未来成熟的 `04_写作知识库` 跨原创作品共享。
- 每部小说的 `project_id / Author Intent / Story State / approved_plan / Decision / 正式正文 / 项目专属资料` 完全隔离。
- 切换作品 = 切换整套原创 project context；上一作品的 Context 不得继续沿用。
- 任何会修改正文、Story State、planning、Decision 的动作，在唯一 project_id 未确定前禁止执行。
- 多作品存在而用户只说“继续写”时不得猜；明确说“继续《作品名》”或“切到《作品名》”时直接解析。
- 不建立全局 `current_project` 文件作为 authority。

## 长篇正文与上下文规则

- 正式正文位于 `03_作品工程/<作品>/03_正文/`，物理存储按章（`第001章.md`、`第002章.md`……）。
- 只有作者明确 acceptance 的版本进入正式正文。
- StoryWrite 运行/acceptance 继续使用稳定 scene/write-turn ref；一个章节可包含多个 accepted ref，不把 scene 强制成文学层级。
- accepted ref 必须可追溯到真实正式正文。
- 每次写作不重读全文：长期连续性用 Story State；未来方向用 active approved_plan；当前任务用 ContextCompiler 少量显式 selection；短期衔接用最近 accepted 正文末尾约 1000–2000 字；久远原文按需定向读取。
- 当前不升级原创全文 RAG / embedding / vector DB。

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
| REAL_PROJECT_WIRING_DESIGN | FROZEN |
| REAL_PROJECT_WIRING_IMPLEMENTATION | READY_FOR_REAL_VERTICAL_SLICE |
| AUTHOR_FACING_ONE_SENTENCE_ENTRY | NOT_YET_PROVEN |
| AUTHOR_FACING_WORKBENCH_DESIGN | ACTIVE |
| UI_DESIGN | NOT_FROZEN |
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
- 不为了测试主动制造真实小说；测试可在 tmp 目录创建最小虚构 fixture
- 不为一次任务新造长期文学 Skill；REAL_PROJECT_WIRING 只允许跨 frozen 能力的最薄机械接线
- 不因当前 UI 讨论直接开发完整 UI 平台

当前阶段允许的是：设计、原型和由真实 UI 需求证明必要的最小补强。

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

**AUTHOR_FACING_WORKBENCH_DESIGN**：

1. 完成“故事发展”交互模式和卡片类型；
2. 合并首页、参考素材、新建作品、创作台、故事地图，形成第一版完整用户流程；
3. 从 UI 核对三个最小基座：
   - candidate / accepted / authority 统一决策机制
   - 状态变化 proposal → confirm/writeback
   - next-best-action（下一步建议）
4. 只有真实 UI 需求证明底层缺能力时才补底层；
5. UI 流程稳定后，再设计 UI → Author Operation Layer → Agent Adapter → Skills 的实际接线。

真实作者纵切尚未完成，因此 `AUTHOR_FACING_ONE_SENTENCE_ENTRY` 不得标记 proven。
