# E2-A｜StoryPlan 定向上游核查与研究记录

> 状态：E2-A 定向核查完成。日期：2026-08-15。
>
> 本记录只回答六个合同问题，不做大型竞品分析；不扩大 GitHub 调研。

## 一、上游核查结果（仅 E1 已确认的五个 donor，均为 pinned commit 实存核验）

| Repo | Pinned commit | 实存核验 | 核查时观察 |
|---|---|---|---|
| `haowjy/creative-writing-skills` | `fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3` | 存在（v0.5.9 release commit） | 仓库此后继续发版；以 pinned 为基线 |
| `Narcooo/inkos` | `8dee4cb2367ec40d986e9a69e4c3ec05e78e79a3` | 存在（feat(skills): ship professional story skill pack） | 仓库活跃；以 pinned 为基线 |
| `ExplosiveCoderflome/AI-Novel-Writing-Assistant` | `3763cd11af4af379e935a655652e76fe98f7f6af` | 存在（merge: promote beta release candidate to main） | 以 pinned 为基线 |
| `worldwonderer/oh-story-claudecode` | `0a34c6998263026ec6160320a89692cdaa53fe69` | 存在（chore(release): v0.7.6） | 仓库活跃；以 pinned 为基线 |
| `anotherpanacea-eng/apodictic` | `3fb7abcdde23915f302e020a29920069a3885fd5` | 存在（Merge PR #225） | 以 pinned 为基线 |

未发现需要因上游变化而调整合同设计的情况；未新增任何 donor。

## 二、每个 donor 实际借用什么 / 明确不采用什么

- **haowjy/creative-writing-skills**：借「作者原话优先保留、AI 补充必须标成假设、探索先于确认、不强制全书预规划」→ 对应 Plan Brief 的 `author_planning_question` 原样保留、`assumptions` 非权威身份、`deliberate_open_space`。**不采用**其多模型角色分工与技能包分发机制。
- **Narcooo/inkos**：借「future branch 与 story truth 分离、planning 文件不是正史、revision/stale 标记」→ 对应 `proposal_noncanonical` + `approved_plan(occurred=false)` + stale 传播。**不采用**其完整 studio/CLI 平台与固定 skill 目录体系。
- **ExplosiveCoderflome/AI-Novel-Writing-Assistant**：借「plan → execute → state feedback 阶段产物可恢复、局部更新而非每次重算整本书」的概念 → 对应 planning item 的 stable id / target_ref / supersedes / built_from 最小接口。**明确不采用**其「AI director 自动完成整本小说」的产品哲学，也不引入卷骨架自动生成。
- **worldwonderer/oh-story-claudecode**：借「reader promise / 钩子与兑现 / 阶段推进作为规划判断维度；近期版本减少上下文与规则堆积」→ 对应 Plan Brief 的判断维度清单（只进 Skill 指导，不进必填字段）。**不采用**其具体章节模板与命令面。
- **anotherpanacea-eng/apodictic**：借「reader contract、reveal economy、诊断问题但不替作者写死解决方案」→ 对应 StoryPlan 的诊断后置原则（先自由规划，真实问题出现才介入 stance/BKP）。**不采用**其风格计量与合同测试基础设施。

## 三、六个合同问题的回答

### 1. StoryPlan 最少需要哪些稳定语义？

project_id、intent_rev / state_rev、planning target（含自由 scope）、规划来源（已确认方向的可追溯 ref）、assumptions 与作者原话分离、`proposal_noncanonical`、作者 Decision、`approved_plan(occurred=false)`、base_state_rev。其余一律不稳定化。

### 2. 哪些东西绝不能提前做成固定 Schema？

book/volume/arc/chapter/scene 五层树；章数、卷名、高潮位点等必填字段；planning item 的类型枚举；dependencies 图结构；任何规划数据库或事件溯源结构。

### 3. 如何表示「未来计划 ≠ 已发生 Canon」？

双层：candidate 一律 `proposal_noncanonical`；经作者 choose/modify 确认后只能 append 进 `approved_plan` 且强制 `occurred=false`。Canon 区域（canon_facts / occurred_events / character_state / relationship_state）只接受 `accepted_text / author_decision / manual_import`，由 E1 runtime 既有 guard 保证。

### 4. 如何支持以后只重做一个局部规划？

本轮只留最小接口：planning item 有 stable `id` 与 `target_ref`；允许 `supersedes` 与 `built_from` ref 字段；Plan Brief 记录 `planning_target`。未来 supersede = 新 diff append 携带 `supersedes: [旧 plan id]`，旧条目可据此标 stale/replace，而不触碰其它 target 的条目。不实现 dependency graph engine。

### 5. 长篇规划除了事件顺序，还必须保留什么？

reader promise/expectation、人物欲望与选择、关系变化、冲突性质变化、suspense/information/reveal、promise/payoff、accumulated consequences、irreversible choices、open threads、阶段结束后故事为何仍有动力。这些是**判断维度**，写入 SKILL.md 指导模型，而不是每个 Plan Node 必填字段。

### 6. 哪些交给强模型、哪些交给确定性 runtime？

模型：规划目标理解、结构判断、维度权衡、deliberate ambiguity 保留、BKP 选卡判断、规划内容本身。Runtime：文件/ID/revision、project 与 ref 一致性、authority 合规、stale 判定、noncanonical 标记、occurred 强制、writeback 门禁、0-knowledge-need 跳过检索、trace/provenance。
