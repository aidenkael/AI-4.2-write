# StoryDesign v0｜能力合同

## 目的

把作者自然语言设想变成一个可讨论的原创故事设计候选，而不是把一句种子直接定成整本书 Canon。

输入可以是“我想写……”“有个故事是……”等自然语言。模型先理解作者意图，明确它补出的 assumptions，由强模型自由完成第一轮原创设计；随后先诊断真实薄弱点，只有存在明确知识缺口时才形成少量 knowledge needs 并调用 KnowledgeRetrieve，显式选择 0–1 张相关 BKP（只有不同卡分别解决不同明确缺口时才允许更多），形成 StoryDesign Context。以单一强模型为主，只在具体缺陷触发时按需切换人物、结构、读者体验等专业 stance。

## 工件与权限

`story_runtime.py` 只管理 ID、revision、authority、stale、BKP provenance、文件和 Diff。它不判断人物魅力、俗套、结局优劣或读者欲望。

每轮产生：

`Author Intent + Story State → Creation Brief → Context Package → proposal_noncanonical candidate → trace`

Candidate 必须标记 `proposal_noncanonical`，不能直接修改 Canon 或 `approved_plan`。作者明确 choose/modify 后才创建 Decision Record；确认的 StoryDesign 方向只能写入 `approved_plan`，仍不等于已发生 Canon。

## 模型执行提示

1. 区分作者明确的输入、当前 Canon、AI assumption 与 BKP 经验。
2. 不为 schema 填满未知项；保留 unknown、multiple candidates 和 intentional ambiguity。
3. BKP 是有 scope/boundary/confidence 的参考，不是处方；模型/Skill 必须显式列出要使用的 card id，runtime 不会按检索排名替它选择。检索返回 OK 不等于必须使用知识卡：相关但没有独立增益的卡必须允许拒绝；`NO_USEFUL_BKP`、`INSUFFICIENT_BKP` 与 0 张 BKP 都是正常结果，标记后继续使用一般创作能力。
4. BKP 用于 challenge、counterexample、gap filling、targeted deepening 和 boundary checking，不负责搭建第一版故事骨架；模型自身已经能解决的问题，不为展示知识库价值重复注入 BKP。
5. 不默认生成分卷、多路线、风险清单、分层揭示、多时钟等固定策划形状；作者可见结果优先保留人物、场景、关系和具体生活质感。trace/provenance 完整保存工程信息，但不强迫作者阅读。
6. 只在复杂问题确有增益时采用额外专业 stance；不得把它们固化为多 Agent 流水线。
7. 把所有新人物、世界规则、谜底和未来事件保留在 proposal，直到作者 Decision。

## CLI

```powershell
python run.py --demo-dir C:\Temp\ai-write-storydesign-demo
```

该入口创建新的 disposable sandbox；它不读取或修改正式作品。
