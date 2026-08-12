# G5-B Agent 任务｜一次性正文与独立诊断

> 状态：待本地执行  
> Gate：G5｜正文诊断与修订最小闭环  
> 子阶段：G5-B  
> 目标：生成一次性短正文，并在没有本轮作者反馈的情况下完成独立 Reader/Critic/Editor 诊断。

## 0. 开始前 Git 安全

先执行只读检查：

- `git fetch origin`
- 当前分支 / `git status --short`
- `git rev-list --left-right --count main...origin/main`
- `git stash list`

要求：

- 不创建新分支；
- 不 `reset / restore / clean / rebase / merge / force push`；
- 不 pop/drop 现有 `stash@{0}`；
- 不处理既有无关 untracked；
- 若本地 `main` 只是落后且工作区条件允许，使用 `git pull --ff-only`；若不能安全 fast-forward，停止并报告，不自行解决历史 dirty。

## 1. 必读权威文件

按顺序读取：

1. `AGENTS.md`
2. `AI-write_长期开发手册.md`
3. `00_项目控制/当前工作索引.md`
4. `00_项目控制/项目阶段门禁.md`
5. `00_项目控制/项目推进记忆.md`
6. `06_工作区/G5A_作者反馈与诊断合同_v0.1.md`
7. `06_工作区/G4B_沙盒_雾港档案室/author_intent.md`
8. `06_工作区/G4B_沙盒_雾港档案室/story_state.yaml`

确认当前 `story_state.yaml` 为 `state_rev=2`。

G4-C 的三份 Context 与 `briefs/brief-001.md` 已 STALE / historical，**只能作为历史证据查看，禁止作为本轮执行上下文直接复用。**

## 2. Borrow-first

只对照两个已确认上游，不扩大搜索：

- `haowjy/creative-writing-skills`
  - 重点理解 Muse / Writer / Critic / Editor / Reader Sim 的职责分离；
  - Critic、Editor、Reader Sim 应从不同角度读取文本，不互相复制结论。
- `anotherpanacea-eng/apodictic`
  - 重点借“文本实际呈现的 contract 与作者意图不一致本身就是诊断信号”；
  - 不需要安装整个插件，不要照搬其完整 schema。

如果网络不可用，已有长期文档中的角色职责足以继续，不因此阻塞。

## 3. 重建本轮 Brief / Context

在：

`06_工作区/G4B_沙盒_雾港档案室/g5b/`

新建：

- `brief_g5b_v1.md`
- `context_g5b_v1.md`

要求：

- built from `intent_rev=1 + state_rev=2`；
- 只取当前场景真正需要的信息；
- 允许从 G4-C 历史材料回看 BKP 来源，但必须重新判断在 `state_rev=2` 下是否仍适用；
- 若使用 BKP，保留来源与边界；
- 不为了证明跨书强行选多书；
- 当前场景计划以 `state_rev=2` 的 `approved_plan` 为准；
- 具体“代价机制”若仍未获得权威确认，只能作为可选创作设计，不可假装 Canon。

## 4. 生成一次性正文 v1

生成：

`g5b/draft_v1.md`

约束：

- 中文短场景，建议约 1200–2000 汉字，够诊断即可；
- 只用于技术验证，不追求正式出版质量；
- 延续沙盒现有设定，不解释最终谜底；
- 重点落实当前 `approved_plan` 的效果目标：读者逐渐感知继续深查存在代价，林昼随后意识到并仍作出选择；
- 具体代价机制可以在正文中提出一个最小、可理解、可被后续推翻的场景实现，但必须在文件头标记为 `sandbox_draft_noncanon`；
- 不修改 `story_state.yaml`；
- 不生成 `accepted_text`。

## 5. 独立诊断：必须先于作者反馈

本轮没有新的作者正文反馈。不要向用户询问“哪里不好”。

建立：

`g5b/diagnostics/reader_sim.md`  
`g5b/diagnostics/critic.md`  
`g5b/diagnostics/editor.md`

三份诊断必须只依据：正文 v1、Author Intent、当前 Story State、Brief/Context 与各自角色职责。

### Reader Sim

只记录实际阅读体验：

- 何时产生好奇、疑惑、情绪、期待、无聊或断裂；
- 哪里开始预判作者意图；
- 哪里担心人物代价，哪里没有形成担心；
- 尽量引用具体文本位置；
- 不负责给完整修订方案。

### Critic

做针对性 craft 诊断：

- 场景目标是否兑现；
- 人物行动是否由人物/情境自然推动；
- 信息揭示与节奏是否有效；
- 是否存在 AI 常见“解释过满、情绪代说、假紧张、过度整齐”等问题；
- 每个 finding 写 evidence + severity + confidence + possible cause；
- 可以提出 solution class，但不直接重写正文。

### Editor

做整体第三方编辑判断：

- 当前场景实际“在写什么”；
- 与 Author Intent / reader promise 是否一致；
- 哪个问题最值得优先改，哪些不值得动；
- 若 Critic 可能过度优化局部，要指出；
- 给 1–3 个高杠杆 revision priority，不写完整改稿。

### 独立性要求

若 Agent 支持子 Agent / 并行 worker，优先分别运行；若不支持，可串行执行，但每个角色在生成自己的报告时**不得读取另外两份诊断**。

不要先生成一个“正确答案”再让三个角色改写成不同口吻。

## 6. Controller 综合

三份独立报告完成后再生成：

`g5b/diagnostic_synthesis.md`

必须包含：

- 诊断共识；
- 明确冲突；
- 只有单一观察者提出的问题；
- 每项的正文 evidence；
- confidence；
- 当前最值得验证的 1–3 个问题；
- 对应的 solution class / revision options；
- 哪些只是 AI 假设，不能当成事实；
- 明确声明：**尚未看到本轮作者反馈，因此不能预测作者会同意什么。**

不要为了显示“多角色有价值”强行制造差异，也不要为了收敛强行抹平差异。

## 7. G5-B 验证报告

生成：

`g5b/G5B_VALIDATION.md`

回答：

1. 是否基于 `state_rev=2` 重建了新 Brief/Context？
2. 是否完全避免复用 STALE Context 作为当前执行输入？
3. draft v1 是否生成且保持 noncanon？
4. Reader/Critic/Editor 是否在无作者反馈下独立完成？
5. 三路诊断有哪些真实共识/冲突？
6. 是否发现一个或多个值得进入 G5-C 让作者实际阅读验证的问题？
7. 是否出现必须升级 Retrieval/BKP/Writer 架构的阻塞？默认应如实回答，不为了 Gate 通过而说没有。
8. Story State 是否前后完全未变？记录文件 SHA256 前后值。

结论只允许：

- `G5-B 技术验证完成候选`；或
- `G5-B BLOCKED` + 具体阻塞。

不得自动进入 G5-C。

## 8. Git 提交范围

只提交 G5-B 本轮新产物，以及如果确有必要的极小任务状态说明；不要顺手改长期手册、门禁、AGENTS 或历史沙盒文件。

提交前：

- `git diff --check`
- 核对 `story_state.yaml` 未修改；
- 核对 `KnowledgeRetrieve` / BKP 未修改；
- 核对既有 untracked 没有被纳入；
- 核对 `stash@{0}` 仍未 pop/drop。

允许 commit + push 到 `main`，前提是远端仍可 fast-forward 且提交范围干净。

## 9. 最终报告格式

最终只报告：

1. Git 同步状态；
2. 新 Brief/Context 路径；
3. draft v1 路径与大致字数；
4. Reader/Critic/Editor 三份诊断路径；
5. Controller synthesis 路径；
6. 最重要的 1–3 个独立诊断结论；
7. Story State 前后 SHA256；
8. 修改文件清单；
9. commit SHA / push 状态；
10. 最终 git status 与 stash 状态；
11. `G5-B 技术验证完成候选` 或 `BLOCKED`。

不要在最终报告里擅自替作者评价“这段已经写得很好”。