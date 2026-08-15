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
| 01_原始素材 | 未经 AI 加工的原始来源 | 原始文件真相 |
| 02_原著蒸馏 | 参考作品结构化知识（BKP） | 参考知识 |
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
| SourcePrepare | AVAILABLE / FROZEN |
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

- 不修改正式小说
- 不修改 Story State
- 不批量蒸馏新书
- 不升级 Retrieval/RAG/KG
- 不实现完整 Writer/Reader/Editor/Controller/UI 平台
- 不为了测试主动制造小说
- 不为一次任务新造长期 Skill

## Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

临时 worktree 默认进入系统 TEMP，不在 E:\ 根留下 AI-Write-*。任务完成后删除 worktree。

## NEXT

真实 author acceptance：
- 作者接受正文 → accepted_text
- 进入 production Story State
- 生成 next Context

不以 Benchmark / Gate / Phase 编号驱动。以真实创作产出驱动。
