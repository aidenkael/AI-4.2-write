# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G4｜创作上下文与作者决策最小闭环：ACTIVE / G4-C。**

G4-A、G4-B 已完成；当前只推进 G4-C。未获用户明确确认，不自动进入 G4-D/E。

开始任务前先读：

1. `00_项目控制/README_目录使用说明.md`
2. `AGENTS.md`
3. `AI-write_长期开发手册.md`
4. `00_项目控制/当前工作索引.md`
5. `00_项目控制/项目推进记忆.md`
6. `00_项目控制/项目阶段门禁.md`
7. 当前专项协议/任务

## 2. 作者交互原则

**作者控制 ≠ 作者审批。**

作者主要通过正文、自然语言反馈和重大取舍控制作品；后台自动负责 Retrieval、Context、Skill 路由、连续性和机械状态维护。

Story State authority：
- `accepted_text:<ref>`；
- `author_decision:<id>`；
- 必要 `manual_import:<source>`。

禁止 BKP / AI candidate / Context Package 直接写 Canon。

## 3. Borrow-first

核心长期参照：AI-Novel-Writing-Assistant、oh-story、creative-writing-skills、Apodictic、InkOS、NovelForge、graphify-novel、ani-book-skill。

能借不自研；不把多个上游 schema 机械合成超级 schema；AI-write 自研集中在协议、路由、胶水、BKP、中文长篇适配、作者控制和必要状态接口。

## 4. G4-C 专项规则

当前沙盒：`06_工作区/G4B_沙盒_雾港档案室/`。

权威工件只有：
- `author_intent.md`
- `story_state.yaml`
- `briefs/brief-001.md`

现有 Retrieval：`05_Skills与自动化/01_Skills/KnowledgeRetrieve/run.py`。

执行任务：`06_工作区/G4C_Agent任务_最小Context与跨书综合.md`。

G4-C 必须真实运行 KnowledgeRetrieve，并至少验证人物、情节/信息、读者体验三类问题。

Context / Retrieval 日志 / Synthesis 报告全部是派生物，不得修改权威 Story State。

## 5. G4-C 禁止

- 不修改 KnowledgeRetrieve 只为提高命中；
- 不升级 embedding / vector DB / reranker / KG；
- 不修改 BookDistill / BKP；
- 不批量蒸馏新书；
- 不强行让两本 BKP 同时出现；
- 不把 Context 或候选方向写进 Canon；
- 不实现完整 Writer / Reader / Critic / Editor；
- 不写正式长篇正文；
- 不自动进入 G4-D。

如果 Retrieval 结果差，原样记录 gap；不要为了“通过”而改基础设施。

## 6. 知识纪律

`Evidence → Observation/Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

单书 Pattern 不直接升级普遍规则。Cross-book Synthesis 要保留不同作品的适用条件、冲突和边界。

## 7. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知本地 dirty / untracked 不清理、不覆盖。已知历史 dirty/untracked 也不为本任务整理。

本任务只 `git add` G4-C 明确产物；不要把无关变化带入 commit。

## 8. 文档纪律

长期手册和项目控制文件只保存稳定原则、当前边界和重大决策；实验日志留在 `06_工作区`。

没有用户明确确认，不自动退出当前子阶段。