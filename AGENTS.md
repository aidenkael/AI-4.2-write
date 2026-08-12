# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G5｜正文诊断与修订最小闭环：ACTIVE / G5-B 待本地验证。**

G0–G4 已关闭。G5-A 已完成反馈与诊断语义校准；当前只执行 G5-B，不自动进入 G5-C/D/E。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项任务。

## 2. 作者交互原则

**作者控制 ≠ 作者审批；作者反馈是信号，不是默认正确的诊断。**

必须区分：

- 作者目标 / 硬约束；
- 作者感觉 / 症状；
- 原因判断；
- 修法建议。

作者控制目标、重大取舍和最终接受；原因判断与修法默认是待验证假设。Agent 应结合正文证据、Reader/Critic/Editor、角色/连续性和相关 BKP 独立判断，必要时有依据地反对作者提出的修法。

同时不得把 AI 诊断包装成唯一客观答案；冲突时保留依据、不确定性和替代解释。

## 3. G4 已验证规则

- Author Intent / Story State / Creation Brief 可文件化恢复；
- Context 小而相关，可重建；revision 变化后旧 Context 必须 STALE；
- Retrieval 只负责召回，Synthesis 属于创作上下文/决策层；
- 跨书知识不强制多书共识；
- `approved_plan ≠ Canon`；
- Story State authority 仅来自合规 `accepted_text / author_decision / manual_import`；
- BKP / AI candidate / Context 不写 Canon。

## 4. G5-B 规则

沙盒：`06_工作区/G4B_沙盒_雾港档案室/`。

当前权威状态：`story_state.yaml@state_rev=2`。

G4-C 的 Context 与 `brief-001` 已 STALE / historical，禁止直接复用。

G5-B 必须先从当前 state 重新编译新 Brief/Context，再生成一次性正文。随后在**没有本轮作者反馈**的情况下分别完成 Reader/Critic/Editor 诊断，最后由 Controller 综合。

这些诊断只分析正文，不获得 `author_decision` authority，也不修改 Story State。

## 5. Borrow-first

优先参照：

- `haowjy/creative-writing-skills`：Muse / Writer / Critic / Editor / Reader Sim 的职责与协作；
- `anotherpanacea-eng/apodictic`：从文本实际效果与作者意图的差异中做诊断。

不要安装或整合大型插件体系只为通过一个测试；只借职责、工作流和必要提示方法。

## 6. 当前禁止

- 不先向作者索要“哪里写错了”；
- 不机械执行作者修法；
- 不让 Reader/Critic/Editor 互相抄答案再假装独立；
- 不复用 STALE Context；
- 不修改正式小说；
- 不修改 Story State；
- 不批量蒸馏新书；
- 不升级 Retrieval/RAG/KG；
- 不实现完整 Writer/Reader/Critic/Editor/Controller 平台；
- 不自动进入 G5-C/D/E。

## 7. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / `stash@{0}` 不清理、不覆盖、不自动 pop/drop。普通同步优先保持单一 `main`，不要为了临时保护留下无意义长期分支。

## 8. 文档纪律

长期文档只保留稳定原则和当前边界；实验细节留在 `06_工作区`。阶段状态以当前索引和门禁为准。