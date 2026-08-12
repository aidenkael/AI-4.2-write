# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**当前无 ACTIVE Gate。G4 已 CLOSED。**

G0–G4 均已关闭。没有用户明确确认新的 Gate 前，不自动继续 G4，也不启动下一阶段实质开发。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项文件。

## 2. 作者交互原则

**作者控制 ≠ 作者审批。**

作者主要通过正文、自然语言反馈和重大取舍控制作品；后台负责 Retrieval、Context、Skill 路由、连续性和状态维护。

Story State 合法 authority：`accepted_text:<ref>`、`author_decision:<id>`、必要 `manual_import:<source>`。

禁止 BKP / AI candidate / Context Package 直接写 Canon。

## 3. G4 已验证规则

- Author Intent / Story State / Creation Brief 可文件化恢复；
- Context 应小而相关，可重建；
- state/intent revision 变化后旧 Context 必须 STALE；
- Retrieval 只负责召回，Synthesis 属于创作上下文/决策层；
- 跨书知识不强制多书共识；
- `approved_plan ≠ Canon`；
- 真实用户自然语言反馈才可成为 `author_decision`；
- 模拟输入只能测试解析，不得写权威状态；
- `reject_all / defer / ambiguity` 默认不写 Story State；
- `accepted_text` 只有文本明确事实可 mechanical settlement，歧义/推断不得自动写回。

G4 的 accepted-text 验证是协议级 dry-run，不代表 Writer/runtime 已接入。

## 4. Borrow-first

核心长期参照：AI-Novel-Writing-Assistant、oh-story、creative-writing-skills、Apodictic、InkOS、NovelForge、graphify-novel、ani-book-skill。

能借不自研；不把多个上游 schema 机械合成超级 schema；AI-write 自研集中在协议、路由、胶水、BKP、中文长篇适配、作者控制和必要状态接口。

## 5. 当前禁止

没有新 Gate 时：

- 不自动开发完整 Writer / Reader / Critic / Editor / Controller；
- 不批量蒸馏新书；
- 不升级 Retrieval/RAG/KG 只为非阻塞 gap；
- 不开发完整 UI、大型数据库或多 Agent 平台；
- 不把 G4 沙盒当正式小说继续写；
- 不新增长期 Schema / Skill taxonomy 只为覆盖单个案例。

## 6. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / stash 不清理、不覆盖、不自动 pop/drop。普通同步优先保持单一 `main`，不要为了临时保护留下无意义长期分支。

## 7. 文档纪律

长期文档只保留稳定原则和当前边界；实验细节留在 `06_工作区`。阶段状态以当前索引和门禁为准。下一 Gate 未确认前，不自行把候选方向写成正式阶段。