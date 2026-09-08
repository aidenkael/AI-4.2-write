# StoryWrite（Go Write 2.0 当前合同）

> 状态：`KEEP_AND_FREEZE` primitives + Go Write 2.0 作者操作接线（2026-09-08）。
> 不新增第二份 Story State、Context 或结算 runtime。

## 职责边界

模型负责语义判断；本层只负责机械合同。当前作者路径是：

1. 说想写什么；
2. 读正文 / 给反馈；
3. 明确接受正文；接受只做 durable 正文写入与作者变更记账，不自动调 AI；
4. 作者显式点击「更新作品状态」后，才对 pending author changes 做有界 Direct AI 语义整合；含糊后果仍由作者确认。

`operations/author_edit` + `operations/change_settlement` 是当前统一作者变更账本/结算路径。下文的 `apply_settlement()` 是冻结的历史薄 primitive，用于合同测试与兼容，不是当前工作台的日常主路径。

## Interactive 执行预算

一次正文写作是一个逻辑任务：一次 UI 动作，最多一次 `/gowrite`。Interactive Stage 1 选择上下文后，桥在同一 request_id 下自动续行 Stage 2；两阶段必须由两个全新、独立上下文的子 Agent 执行。Stage 2 只能看见确定性编译后的精确 Context，不得承接 Stage 1 会话。

## 三个自动化摇柄（按优先级）

| 优先级 | 摇柄 | 函数 | 替代的手工动作 |
| --- | --- | --- | --- |
| P0 | MECHANICAL_SETTLEMENT_ASSIST | `apply_settlement()` | 手工构造 shadow/next Story State JSON |
| P1 | Brief / Context preparation | `prepare_creation_brief()` / `prepare_context()` | 手写 creation_brief.json + 一次性编译脚本 |
| P2 | recent prose window | `prepare_recent_prose_window()` | 手工截取上一场末段并标注权威 |

全部实现为对冻结合同的薄透传 / 薄守卫：

- Story State 结构与 `validate_story_state` 原样复用（E1）；
- Creation Brief 原样复用 `compile_creation_brief`（E1）；
- Context 原样复用 E3-A `compile_context`：显式 selection、空 selection 不 fallback、BKP 冻结门；
- 不复制任何 Context Compiler / StoryPlan 逻辑。

## 结算三分类门（P0 纪律）

- 只有 `mechanical`（正文明确成立的话语/动作本身）可能进入 Story State；
- `ambiguous` / `creative` 只进入报告的 `not_writable`，任何 mode、任何 flag 下都不得写入；
- authority 由 runtime 铸造，模型不得自选：
  - `production`：必须显式 `author_accepted=True` + `accepted_scene_ref`，铸造 `accepted_text:<scene_ref>`；未获接受的实验稿（FROZEN EXPERIMENT DRAFT）不得因本工具存在而升级；
  - `shadow`：只允许 `manual_import:` 前缀（如 `manual_import:experiment_shadow_from_W2`），不得声称 acceptance；
- simulation/test source 不得伪装 production authority：新输入中携带
  `author_decision:` / `accepted_text:` 前缀且含 simulation/test 标记的一律拒绝
  （历史 `author_decision:storydesign-simulated` 仅作历史证据，不回改）。

### 模型侧 hard-anchor 检查（F0-2 补强）

完成 mechanical / ambiguous / creative 分类后，模型必须额外扫描正文中的**continuity-critical hard anchors**：

- 明确数字（价格、账期、数量、比例、期限）；
- 日期 / 时间 / deadline；
- 合同条件；
- 明确承诺（“我会……”、“三天以内……”）。

只有正文明确成立且未来可能约束连续性的 hard anchor 才进入 mechanical。
这类事实不在 State、不在 recent prose 窗口时，下一场正文就会产生数字冲突。

**这不是规则引擎 / NLP 提取器**——是模型判断时的额外检查步骤，不增加任何
runtime 代码。第三场暴露的“两个月账期”结算遗漏即此类型。

## recent prose 窗口（P2 纪律）

- 简单尾部窗口，目标量级约 1000–2000 中文字，优先最近一场末段；
- 非权威派生输入（`is_authority: false` / `must_not_write_state: true`）；
- 无 RAG、无 embedding / vector DB；
- 附带最小写作提示：吸收短时连续性，但不得逐字复写上一场表达；不建立新"文风系统"。

## BKP 策略

继续 `BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`：无明确 knowledge need 不调用
KnowledgeRetrieve（由冻结 E1 门保证，本层不绕过）。

## 测试

`test_storywrite_entry.py`：三分类门、acceptance 门、simulation 伪装守卫、
rev/authority/既有 id 约束、recent prose 非权威、Context 显式选择无 fallback。

回归：ContextCompiler / StoryPlan / StoryDesign 测试套件保持全绿，本层不修改
任何冻结子系统。
