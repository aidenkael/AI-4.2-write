# AI-write Agent 长期规则

> 面向进入仓库工作的 Agent / Codex。目标是让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**G4｜创作上下文与作者决策最小闭环：ACTIVE / G4-C。**

G4-A、G4-B 已完成；G4-C 已完成真实本地验证，当前是**技术验证完成候选，等待用户确认是否进入 G4-D**。未获确认，不重复执行 G4-C，也不自动进入 G4-D/E。

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

## 4. G4-C 已验证事实

沙盒：`06_工作区/G4B_沙盒_雾港档案室/`。

权威工件仍只有：
- `author_intent.md`
- `story_state.yaml`
- `briefs/brief-001.md`

验证报告：`g4c/G4C_VALIDATION.md`。  
验证提交：`cf6ed32b9de8a372e25c00a50840756b905f12c3`。

已证明：

- 真实 KnowledgeRetrieve 可用；
- 小 Context 可覆盖人物、情节/信息、读者体验三类问题；
- 不必每次强制跨书；
- Q3 有真实跨书互补；
- 亲属哀伤/内疚存在 BKP gap，但不阻塞；
- 当前无需 Retrieval/RAG/KG 升级；
- Context / Synthesis 未污染 Story State。

## 5. 当前禁止

- 未确认前进入 G4-D；
- 重跑 G4-C 只为得到更漂亮结果；
- 为非阻塞 gap 批量蒸馏新书；
- 修改 KnowledgeRetrieve 只为提高命中；
- 升级 embedding / vector DB / reranker / KG；
- 修改 BookDistill / BKP；
- 把 Context 或候选方向写进 Canon；
- 实现完整 Writer / Reader / Critic / Editor；
- 写正式长篇正文。

## 6. 知识纪律

`Evidence → Observation/Inference → Work-specific Pattern → Cross-book Pattern → Creation-tested Heuristic → Production Rule`

单书 Pattern 不直接升级普遍规则。Cross-book Synthesis 要保留不同作品的适用条件、冲突和边界；没有真实跨书就不要制造跨书。

## 7. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / stash 不清理、不覆盖、不自动 pop/drop。先识别内容，再决定处理方式。

## 8. 文档纪律

长期手册和项目控制文件只保存稳定原则、当前边界和重大决策；实验日志留在 `06_工作区`。

没有用户明确确认，不自动退出当前子阶段或进入下一子阶段。