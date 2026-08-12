# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G4｜创作上下文与作者决策最小闭环：ACTIVE / G4-D。**

G4-A/B/C 已完成；当前只推进 G4-D。未获用户明确确认，不自动进入 G4-E。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项文件。

## 2. 作者交互原则

**作者控制 ≠ 作者审批。**

作者主要通过正文、自然语言反馈和重大取舍控制作品；后台负责 Retrieval、Context、Skill 路由、连续性和状态维护。

Story State 合法 authority：`accepted_text:<ref>`、`author_decision:<id>`、必要 `manual_import:<source>`。

禁止 BKP / AI candidate / Context Package 直接写 Canon。

## 3. G4-D 专项规则

沙盒：`06_工作区/G4B_沙盒_雾港档案室/`。

当前真实验证入口：`g4d/G4D_作者决策真实验证.md`。

要求：

- 真实用户自然语言反馈才能成为 `author_decision`；
- Agent/测试脚本模拟的 choose/modify/reject/defer 只能验证解析，不得写权威状态；
- `reject_all / defer` 默认不改 Story State；
- 作者修改未来场景方向时，必要写回只更新 `approved_plan` 等未来计划，不把计划伪装成 occurred Canon；
- 没有已接受正文时禁止制造 `accepted_text` mechanical settlement；
- 有歧义时停止写回并请求澄清；
- Decision Record / Diff 由后台生成，作者不填表；
- Diff 必须匹配当前 `base_state_rev`。

## 4. 已验证前提

G4-C 已证明：真实 KnowledgeRetrieve 可运行；小 Context 覆盖人物、情节/信息、读者体验；跨书按问题自然发生；当前无 Retrieval/RAG/KG 升级理由。

## 5. 当前禁止

- 自动替作者选创作方向；
- 用模拟用户输入获得 authority；
- 为测试而强制修改 Story State；
- 实现完整 Writer / Reader / Critic / Editor；
- 批量蒸馏新书；
- 升级 Retrieval/RAG/KG；
- 自动进入 G4-E。

## 6. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

历史 local dirty / untracked / `stash@{0}` 不清理、不覆盖、不自动 pop/drop。本阶段不为它们创建临时分支；需要处理时先识别内容。

## 7. 文档纪律

长期文档只保留稳定原则和当前边界；实验细节留在 `06_工作区`。阶段状态以当前索引和门禁为准。