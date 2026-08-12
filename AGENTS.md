# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G5｜正文诊断与修订最小闭环：ACTIVE / G5-C。**

G0–G4 已关闭。G5-A/B 已完成；当前只推进 G5-C，不自动进入 G5-D/E。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项工件。

## 2. 作者交互原则

**作者控制 ≠ 作者审批；作者反馈是信号，不是默认正确的诊断。**

必须区分：

- 作者目标 / 硬约束；
- 作者感觉 / 症状；
- 原因判断；
- 修法建议。

作者控制目标、重大取舍和最终接受；原因判断与修法默认是待验证假设。Agent 应结合正文证据、Reader/Critic/Editor、角色/连续性和相关 BKP 独立判断，必要时有依据地反对作者提出的修法。

同时不得把 AI 诊断包装成唯一客观答案；冲突时保留依据、不确定性和替代解释。

## 3. 已验证规则

G4 已证明：

- Author Intent / Story State / Creation Brief 可文件化恢复；
- Context 小而相关，可重建；revision 变化后旧 Context 必须 STALE；
- Retrieval 只负责召回，Synthesis 属于创作上下文/决策层；
- 跨书知识不强制多书共识；
- `approved_plan ≠ Canon`；
- Story State authority 仅来自合规 `accepted_text / author_decision / manual_import`；
- BKP / AI candidate / Context 不写 Canon。

G5-B 已证明：

- 可从 `state_rev=2` 重建新 Brief/Context，而不复用 STALE Context；
- 可生成一次性 noncanon 正文；
- Reader Sim / Critic / Editor 能在没有作者本轮反馈时分别独立诊断正文；
- Controller 能保留共识、冲突、单一路径观察和不确定性；
- Story State 保持不变；当前无 Retrieval/BKP/Writer 架构阻塞。

## 4. G5-C 规则

当前正文：`06_工作区/G4B_沙盒_雾港档案室/g5b/draft_v1.md`。

当前独立诊断已经完成，但在作者本轮反馈形成前，不应额外展开完整诊断去锚定作者。

收到真实作者反馈后：

1. 保留原话；
2. 拆分 goal/constraint、symptom/experience、diagnosis、remedy；
3. 与已有 Reader/Critic/Editor 报告和正文 evidence 三角校验；
4. 输出 agree / partly_agree / disagree / uncertain，并说明依据；
5. 若作者修法不合适，给出更小、更贴目标的替代方向；
6. 不为了证明 AI 有价值而故意唱反调；
7. 只对确认值得处理的问题生成小修订；
8. 修订稿仍为 sandbox/noncanon，作者接受前不得产生 accepted_text 或修改 Story State。

## 5. 模型/执行推荐纪律

优先减少用户操作：一个任务尽量只推荐一个 Agent、一个模型、一次操作。

- 代码、架构、跨文件工程、脚本调试、Git/CI、本地运行占主导：可以优先推荐 Codex；
- 正文阅读、文本提取、总结归纳、章节分析、BKP 蒸馏、文学诊断占主导：不要优先推荐 Codex，选更适合中文长文本理解的模型；
- 混合任务按主任务选择一个模型，不做无必要的细碎拆分；只有明显质量/风险收益时才拆。

推荐时写清：执行者、模型、思考强度、备选/升级条件。

## 6. Borrow-first

优先参照：

- `haowjy/creative-writing-skills`：Muse / Writer / Critic / Editor / Reader Sim 的职责与协作；
- `anotherpanacea-eng/apodictic`：从文本实际效果与作者意图的差异中做诊断。

不要安装或整合大型插件体系只为通过一个测试；只借职责、工作流和必要提示方法。

## 7. 当前禁止

- 不先向作者索要“正确诊断”；
- 不机械执行作者修法；
- 不把完整 AI 诊断提前灌给作者以引导其本轮反馈；
- 不复用 STALE Context；
- 不修改正式小说；
- 不修改 Story State；
- 不把 draft v1 当 accepted text；
- 不批量蒸馏新书；
- 不升级 Retrieval/RAG/KG；
- 不实现完整 Writer/Reader/Critic/Editor/Controller 平台；
- 不自动进入 G5-D/E。

## 8. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / `stash@{0}` 不清理、不覆盖、不自动 pop/drop。普通同步优先保持单一 `main`，不要为了临时保护留下无意义长期分支。

## 9. 文档纪律

长期文档只保留稳定原则和当前边界；实验细节留在 `06_工作区`。阶段状态以当前索引和门禁为准。