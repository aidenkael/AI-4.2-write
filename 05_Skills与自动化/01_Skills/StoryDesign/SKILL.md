# StoryDesign v0｜能力合同

## 目的

把作者自然语言设想变成一个可讨论的原创故事设计候选，而不是把一句种子直接定成整本书 Canon。

输入可以是“我想写……”“有个故事是……”等自然语言。模型先理解作者意图，明确它补出的 assumptions，再决定真正需要解决的创作问题和少量 knowledge needs。必要时调用 KnowledgeRetrieve，选择少量相关 BKP，形成 StoryDesign Context，并以单一强模型为主按需切换人物、结构、读者体验等专业 stance。

## 工件与权限

`story_runtime.py` 只管理 ID、revision、authority、stale、BKP provenance、文件和 Diff。它不判断人物魅力、俗套、结局优劣或读者欲望。

每轮产生：

`Author Intent + Story State → Creation Brief → Context Package → proposal_noncanonical candidate → trace`

Candidate 必须标记 `proposal_noncanonical`，不能直接修改 Canon 或 `approved_plan`。作者明确 choose/modify 后才创建 Decision Record；确认的 StoryDesign 方向只能写入 `approved_plan`，仍不等于已发生 Canon。

## 模型执行提示

1. 区分作者明确输入、当前 Canon、AI assumption 与 BKP 经验。
2. 不为 schema 填满未知项；保留 unknown、multiple candidates 和 intentional ambiguity。
3. BKP 是有 scope/boundary/confidence 的参考，不是处方；模型/Skill 必须显式列出要使用的 card id，runtime 不会按检索排名替它选择。无有效命中时标记 `INSUFFICIENT_BKP` 后继续使用一般创作能力。
4. 只在复杂问题确有增益时采用额外专业 stance；不得把它们固化为多 Agent 流水线。
5. 把所有新人物、世界规则、谜底和未来事件保留在 proposal，直到作者 Decision。

## CLI

```powershell
python run.py --demo-dir C:\Temp\ai-write-storydesign-demo
```

该入口创建新的 disposable sandbox；它不读取或修改正式作品。
