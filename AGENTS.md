# AI-Write Agent 长期规则

> 面向进入仓库工作的 Agent。目标是让后台复杂度服务作者，作者不管理系统。

## 当前阶段

**CURRENT_PHASE = REAL_WRITING_USAGE**

**PRODUCT_BASELINE = GO_WRITE_2_0_APPROVED**

工作台已从开发验证期进入真实使用期。主目标是辅助作者进行长篇小说创作。

## 核心目标

让后台复杂度服务作者。日常创作界面中，作者不管理 Prompt / Agent / Skill / Schema / Context ID；「设置」页面允许作者真实配置 AI 服务/API、模型、Agent 与任务执行配置。

作者应使用自然语言表达“新建/继续/切换作品、构思、规划、写、修改、确认方向、接受正文”；Agent 负责识别后台能力。不要要求作者记 StoryDesign / StoryPlan / ContextCompiler / KnowledgeRetrieve / StoryWrite 名称，也不要要求作者维护一组 Skill Prompt 模板。

## 作者侧产品规则

- 后台按成熟作者标准工作，前台按普通新手可理解的方式交流。
- 日常创作界面中，作者操作作品和创作任务，不需要每次选择 Agent、模型或 Skill；「设置」页面允许作者真实配置 AI 服务/API、模型、Agent 与任务执行配置。Agent 是 AI-write 执行 Skills 和复用知识库的重要执行层。
- 高频明确操作可以按钮化；模糊和创造性需求保留自然语言。
- candidate / draft / proposal 默认不是 authority，作者明确采用后才能正式写入。
- 六页是同一作品的六个作者任务，不是六个独立事实仓库：作品概览仅状态+下一步；作品地基拥有关系/人物等源表示；故事地图仅派生可视化（关系图/时间事件/未解决线索），不重复地基列表；同一原始列表不得多页重复呈现。
- 统一变更循环是目标合同：作者编辑/接受 → delta → 确定性处理 → 需要时 AI 增量语义结算 → 安全 writeback → 派生视图刷新；接入完成前 UI 不得伪造编辑/结算入口。作者编辑与 AI 接受一律进入统一作者变更账本与结算路径（`operations/author_edit` + `operations/change_settlement`）；关系/时间/伏笔/状态更新共享同一条结算路径，不建第二套同步 runtime；Story Map 的编辑入口必须路由到与作品地基相同的源操作。
- **Go Write 2.0 是正式产品基线。**它面向中文长篇小说作者；固定作品管理框架，具体工作内容结构随作品与任务动态生长。稳定的作品一级页面为「作品概览 / 作品地基 / 故事规划 / 正在写 / 故事地图 / 作品检查」。
- UI 1.0 保留为已验证的技术纵切/实现参考基线；其与 Go Write 2.0 冲突的产品假设已被 supersede，但历史记录不得删除。
- 字数规划是 Go Write 2.0 的一等能力：总目标 → 卷/阶段预算 → 章节范围 → 实际字数。它是已批准的产品方向，不因本条规则自动宣称已经实现。
- AI candidate / draft / proposal 仍非 authority；未来规划不等于 Canon；作者编辑须先进行影响分析并走安全的 authority/writeback 合同，不得直接、无保护地改写 Canon。

## 目录 authority

| 目录 | 职责 | Authority |
|---|---|---|
| 01_原始素材 | 未经 AI 加工的原始来源 + 素材资产.json（canonical ledger；含 REFERENCE_WORK / RESEARCH / LOOSE_MATERIAL / METHOD_SOURCE / NEEDS_REVIEW） | 原始文件真相 + canonical registry |
| 02_素材知识库 | 与来源绑定的外部知识：参考作品 `<asset>/bkp`（BKP）与方法/技巧资料 `<asset>/method`（方法知识包） | 来源绑定参考知识 |
| 03_作品工程 | 原创小说作品 | **原创最高 authority** |
| 04_写作知识库 | 经多作品验证的长期写作知识；可调用包必须为 FINALIZED_VALIDATED（identity.json + validation.md + knowledge/cards.md） | 跨作品经验 |
| 05_Skills与自动化 | 工作台可调用能力 | capability |
| 06_工作区 | 临时运行空间 | derivative/temp |
| 07_工作台应用 | 正式作者侧桌面应用（UI、接口、Agent 接入、应用层） | 产品/应用层 |

## 创作 authority 顺序

1. 作者当前明确决定
2. 作者接受正文 / production Story State
3. 当前有效规划（active planning）
4. 参考知识 BKP / 04 knowledge

**BKP 不得成为原创 Canon。** 02/04 的外部知识（参考作品 BKP / 方法知识 / 已验证知识）可以影响 proposal/写作/检查，但永远不能写入或覆盖项目 Canon / Story State authority。未接受文本不得进入 production 正文/State。
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
| MaterialIntake | CANONICAL_CATALOG_AVAILABLE + INTAKE_AND_WRITEBACK_AVAILABLE（素材资产.json = 唯一 canonical 真源；CSV/MD derived；类型含 METHOD_SOURCE） |
| SourcePrepare | AVAILABLE（canonical ledger consumer；index_builder 已退役） |
| MethodPrepare | AVAILABLE（METHOD_SOURCE 确定性预处理；无模型；产物 06_工作区 Local Only） |
| BookDistill | AVAILABLE / FROZEN |
| MethodDistill | AVAILABLE（方法知识蒸馏 + 确定性定稿；方法取向合同，非 BookDistill 换标签） |
| KnowledgeRetrieve | AVAILABLE（统一多源：参考 BKP / 方法知识 / 已验证知识一次调用混合检索；不再是旧版 BKP-only 冻结实现） |
| StoryDesign | CLOSED / FROZEN |
| StoryPlan | CLOSED / FROZEN |
| ContextCompiler | CONSUMER_DRIVEN_FREEZE |
| StoryWrite primitives | KEEP_AND_FREEZE |
| Mechanical settlement assist | KEEP_AND_FREEZE |
| REAL_PROJECT_WIRING_DESIGN | FROZEN |
| REAL_PROJECT_WIRING_IMPLEMENTATION | READY_FOR_REAL_VERTICAL_SLICE |
| AUTHOR_FACING_ONE_SENTENCE_ENTRY | NOT_YET_PROVEN |
| AUTHOR_FACING_WORKBENCH_DESIGN | ACTIVE |
| PRODUCT_BASELINE | GO_WRITE_2_0_APPROVED（产品基线已批准；未实现能力不得标记 DONE） |
| UI_1_0_BASELINE | TECHNICAL_VERTICAL_SLICE_REFERENCE（历史技术/实现参考；非正式产品基线） |
| WRITER_PLATFORM_REQUIRED | NO |

## 方法链与知识检索（两条生产分支 + 统一入口）

```text
REFERENCE_WORK → SourcePrepare → BookDistill → 02_素材知识库/<asset>/bkp
METHOD_SOURCE  → MethodPrepare → MethodDistill → 02_素材知识库/<asset>/method
```

参考作品链：`SourcePrepare → BookProfile → 多视角 Discovery → 按需 Deep Dive → BookDistill 收敛 → BKP → KnowledgeRetrieve`

方法/技巧资料链：`MethodPrepare（确定性，无模型）→ MethodDistill（语义抽取 + 确定性定稿）→ 方法知识包 → KnowledgeRetrieve`

检索是统一多源入口：一次 `KnowledgeRetrieve.retrieve(query)` 加载并搜索全部已启用来源（`reference_bkp` / `method_source` / `validated_knowledge`），返回单一混合 RetrievalPackage；模型不选择“先查哪个库”，命中统一用 `selection_ref = <source_kind>/<source_id>/<source_anchor>`；生产请求/Context 使用 `selected_knowledge_refs / selected_knowledge_hits`。不建 KnowledgeRouter / 向量库 / embedding / KG / 新模型调用。
方法卡 `capability_candidate=true` 仅表示潜在可执行的方法知识，绝不自动创建/晋升 05 侧 Skill；方法源绝不自动进入 04；05 Skill 晋升是独立的、证据/测试驱动的人工过程。
作者面只有一个素材入口：UI 只传素材 id，后端按素材类型分派提纯/蒸馏（按钮只写「提纯 / 蒸馏」）。

## 02/04 边界与单书约束

BKP 长期保存作品身份、作品地图、BookProfile、Observation、Inference、Pattern、Deep Dive 和可追溯 Evidence。

单书 BKP 不自动升级为普遍写作规则。BKP 策略：`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`。

## Context 规则

- 仅显式选择，空 selection 不 fallback 整包
- State selection 必须 explicit
- Context Package 是可重建派生层，不是 authority

- 每个 project-page 数据合同必须在共享边界规范化/校验；项目页面不得因加载或切换状态崩溃，修改共享项目 UI 合同时必须保留六页挂载烟测。

## 开发原则

`CAPABILITY_FIRST_CONSUMER_DRIVEN`：冻结子系统没有真实 consumer blocker 不重开。

开发决策规则：只有同时满足（1）真实使用暴露问题；（2）问题重复或严重；（3）现有能力不能低成本解决；（4）新代码能明显降低长期负担，才允许建议新 runtime。否则 DO_NOT_BUILD。

窄口径：`THIN_ORCHESTRATION_BUILD_ALLOWED`——只允许复用现有合同的薄操作层；不代表完整通用 Writer platform 获批（AI-write 作者侧桌面工作台 1.0 已批准进入实现）。

执行边界（详见 `00_项目控制/长期开发手册.md` §15）：

- 确定性工作一律 Code first；
- 一次模型调用即可完成的单轮语义工作 Direct AI first；
- 只有需要模型引导的工具/Skill/多步骤执行才使用 Agent；
- Author / Code / Direct AI / Agent 全部消费同一项目 authority 与派生快照，不建第二份状态；
- 没有真实使用证明的 consumer blocker，不新增大型 AI 编排框架。

## Borrow-first

`真实问题 → 查成熟上游 → 能借就借 → 最小适配 → 真实运行`

当前优先参照：
- oh-story / AI-Novel-Writing-Assistant：长篇运行、拆文
- creative-writing-skills：Reader / Craft
- Apodictic：Developmental Editing
- ani-book-skill：evidence-first、权威工件

许可与复用规则：
- 成熟技术不重新验证；能直接使用成熟 MIT/BSD/Apache 等宽松许可组件时优先使用。
- 同类 AGPL/GPL 项目主要借架构、产品思路、交互设计。
- 复制具体代码前必须再次核验对应版本/文件的许可证。
- 不要因为 GitHub 有代码就自动复制。

## 当前禁止

- 未获得作者明确 acceptance / decision 时，不得修改 production 正文或 Story State
- 作者明确接受正文或作出创作决定后，允许按照现有 authority / writeback 合同更新
- AI 自己的草稿、推测、candidate、Context、Brief 不得自动升级为 production authority
- 不批量蒸馏新书，不批量蒸馏方法书（提纯/蒸馏都是作者显式动作）
- 不升级 Retrieval/RAG/KG（统一多源检索保持轻量确定性：无向量库/embedding/KG/新模型调用）
- 不从 MethodDistill 自动创建/晋升任何 05 侧 Skill；方法源不自动进入 04
- 不建设完整通用 Writer/Reader/Editor/Controller 平台（AI-write 作者侧桌面工作台 1.0 已批准进入实现，属例外）
- 不为了测试主动制造真实小说；测试可在 tmp 目录创建最小虚构 fixture
- 不为一次任务新造长期文学 Skill；REAL_PROJECT_WIRING 只允许跨 frozen 能力的最薄机械接线
- 除已批准的 Go Write 2.0 作者侧工作台方向外，不因 UI 讨论开发其他完整平台

当前阶段允许的是：按 Go Write 2.0 正式产品基线、并参考 UI 1.0 技术纵切实现 07_工作台应用，以及由真实 UI 使用证明必要的最小底层补强。

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
| METHOD_PREPARE | MethodPrepare 完成（确定性，无模型）且目录刷新成功 | 仅三份 material state files（产物在 `06_工作区/MethodPrepare/`，Local Only） |
| METHOD_DISTILL | 方法包定稿 `FINALIZED_RETRIEVAL_READY` + 全部定稿校验通过 + 目录刷新成功 | 当前 asset 的单一方法子树（`02_素材知识库/<asset_id>_<名称>/method/`）+ 三份 material state files |

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

里程碑以 `00_项目控制/长期开发手册.md` §16 为唯一定义：

- **M1 AUTHOR_UX_BLOCKERS**：编辑器底部动作永远可达；退役记录可见可恢复（同一 ref）；六个作品页面保持 runtime-safe。
- **M2 DIRECT_AI_SEMANTIC_V1**：最小独立模型 API 路径；只迁移 change_settlement 高频语义；日常语义维护不再经过 Agent /gowrite。
- **M3 KNOWLEDGE_GROUNDED_FOUNDATION_DESIGN**：垂直切片已实现（见手册 §18）；重大新书/基座设计保持 Agent 主导（分解基座问题、多轮 KnowledgeRetrieve、综合提案、作者确认后写回）。
- **M4 FULL_AUTHOR_LOOP_ACCEPTANCE**：真实运行时纵切验收完成（见手册 §19）；idea → foundation → planning → outline → prose → acceptance → 自动语义维护 → map/state 刷新 → 作者编辑 → 重新结算 → 下一次写作使用最新状态。

除非新架构/产品模块阻塞 M1-M4 之一，否则不批准。真实作者完整纵切尚未完成，因此 `AUTHOR_FACING_ONE_SENTENCE_ENTRY` 不得标记 proven。
