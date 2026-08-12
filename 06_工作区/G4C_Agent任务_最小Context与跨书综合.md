# G4-C Agent 任务｜最小 Context + Cross-book Synthesis

> 本任务只执行 G4-C。不要扩大到 G4-D、Writer、UI、Retrieval 升级或新架构。

## 1. 本次唯一目标

使用**现有** G4-B 沙盒状态、两份正式 BKP 和现有 `KnowledgeRetrieve`，真实验证：

`Author Intent + Story State + Creation Brief + 少量 BKP Hit → 小而相关 Context Package → 1～3 个情境化创作方向`

至少覆盖三类创作问题：

1. 偏人物；
2. 偏情节 / 信息；
3. 偏读者体验。

本任务不写完整正文，不修改 Canon，不验证最终小说质量。

---

## 2. 开始前必须做

先按仓库规则阅读：

1. `00_项目控制/README_目录使用说明.md`
2. `AGENTS.md`
3. `AI-write_长期开发手册.md`
4. `00_项目控制/当前工作索引.md`
5. `00_项目控制/项目推进记忆.md`
6. `00_项目控制/项目阶段门禁.md`
7. `00_项目控制/G4_启动记录_2026-08-12.md`
8. `06_工作区/G4A_最小创作合同_v0.1.md`
9. 本文件

然后执行并记录：

```bash
git status --short
git branch --show-current
git fetch origin
git rev-list --left-right --count main...origin/main
```

要求：

- 不清理任何既有 dirty / untracked；
- 不执行 reset / restore / clean / rebase / merge / force push；
- 如果本地 main 落后且无法安全 `git pull --ff-only`，停止并报告；
- 不把与本任务无关的已有变化纳入提交。

已知历史 dirty/untracked 不是本任务待办。

---

## 3. 权威输入

沙盒：`06_工作区/G4B_沙盒_雾港档案室/`

只把下面三份视为原创权威输入：

- `author_intent.md`
- `story_state.yaml`
- `briefs/brief-001.md`

`RECOVERY_CHECK.md` 只是验收报告，不是 Story State。

正式 BKP 当前只有：

- `02_原著蒸馏/book_0038_一九八四/`
- `02_原著蒸馏/book_0065_三体/`

现有 Retrieval：

`05_Skills与自动化/01_Skills/KnowledgeRetrieve/run.py`

其 CLI 已支持：

```bash
python run.py --list-books
python run.py --stats
python run.py "创作问题"
```

不要先修改它。

---

## 4. 先确认现有 Retrieval 能真实运行

在 KnowledgeRetrieve 目录运行：

```bash
python run.py --list-books
python run.py --stats
```

确认能加载当前两份 BKP。

如果运行失败：

- 先判断是路径/环境/本地同步问题还是代码真实 bug；
- 不做架构升级；
- 如果只是当前本地状态阻塞，报告；
- 只有一个极小、明确、阻塞 G4-C 的 bug 才允许提出修复，修复前先说明原因，且不得借机重构 Retrieval。

---

## 5. 三个真实检索问题

基于同一份 `brief-001`，分别运行以下问题。允许在不改变语义的情况下做一次关键词更清楚的重述，但必须同时保留原问题与实际运行 query。

### Q1｜偏人物

> 人物面对与已故亲人有关的异常证据时，怎样让内疚、回避和主动选择共同推动行动，而不是靠外部事件强推？

### Q2｜偏情节 / 信息

> 一个异常档案的提交日期晚于人物死亡日期，怎样逐步释放信息和悬念，让每次揭示改变人物选择，同时不一次解释完谜底？

### Q3｜偏读者体验

> 怎样让读者从“工作异常”逐渐进入“私人刺痛 → 好奇 → 担心人物会付出什么代价”，同时保持悬念和情绪递进？

每个 query 都必须真实运行 `python run.py "..."`。

把原始输出保存到沙盒派生目录，例如：

`06_工作区/G4B_沙盒_雾港档案室/g4c/retrieval/`

文件名可简洁，但必须能对应 Q1/Q2/Q3。

---

## 6. 语义选择规则

KnowledgeRetrieve 只负责候选召回，Agent 负责语义选择。

对每个 query：

1. 先读当前 Author Intent / Story State / Brief；
2. 从 Retrieval 候选中只保留真正相关的少量条目；
3. 建议每个 Context 最终 BKP Hit **0～5 条**，不是越多越好；
4. 保留每个 Hit 的：作品、知识条目定位、Evidence（若输出有）、Scope、Boundary、Counterevidence、Confidence；
5. 说明“为什么此时相关”；
6. 同时记录明显被排除的高排名噪音及排除理由（只需少量典型项）；
7. 如果只有一本书真正相关，就只用一本；
8. 如果两本都相关，说明互补、冲突或条件差异；
9. 如果没有真正相关知识，明确 `INSUFFICIENT_BKP / gap`，不得硬凑。

禁止：

- 因为要验证“跨书”就强制一九八四 + 三体各选一条；
- 把单书 Pattern 说成普遍规则；
- 只看关键词分数，不做语义判断；
- 为了结果漂亮去改 Retrieval。

---

## 7. 构建三个最小 Context Package

建议放在：

`06_工作区/G4B_沙盒_雾港档案室/g4c/contexts/`

分别对应 Q1/Q2/Q3。

每份 Context 最少包含：

- `context_id`；
- `built_from`：intent_rev / state_rev / brief_id/rev + Retrieval 输出引用；
- `problem_lens`；
- `selected_intent`：只摘与该问题直接有关的 1～3 项；
- `selected_story_state`：只引用必要 Canon / character / relation / event / thread / approved_plan；
- `selected_bkp_hits`；
- `why_selected`；
- `excluded_or_irrelevant`；
- `conflicts_or_boundaries`；
- `gaps`；
- `synthesis`；
- `candidate_directions`：1～3 个真正有差异的方向。

Context 必须是**派生物**，文件内显式写：

`authority: derived_context_only`

不得修改 `story_state.yaml`。

---

## 8. 候选方向的最低要求

每个方向至少说明：

- 它具体改变当前场景设计的什么；
- 为什么适合当前人物 / 状态 / Reader Promise；
- 用到了哪些 BKP 经验；
- 主要风险 / 代价；
- 适用边界或不确定性。

如果 2～3 个方向只是换措辞，视为失败。

候选方向不是作者决定，不生成 State Diff，不写 approved_plan。

---

## 9. G4-C 验证报告

创建：

`06_工作区/G4B_沙盒_雾港档案室/g4c/G4C_VALIDATION.md`

尽量短，必须回答：

1. 三个 query 的真实运行结果状态；
2. 每类问题最终选了多少 State 条目、多少 BKP Hit；
3. Context 是否明显小于“全量状态 + 全量 BKP”；
4. 哪些 Hit 真有帮助，哪些只是关键词噪音；
5. 是否出现真正的跨书互补/冲突；若没有，明确写没有；
6. 1～3 个方向是否有真实差异；
7. 是否发现 BKP knowledge gap；
8. 是否发现必须升级 Retrieval 的**阻塞性**问题；
9. 是否修改过 Author Intent / Story State / Brief（正常答案应为否）；
10. G4-C 是否可标记“技术验证完成候选”，以及理由。

不要写长篇研究报告。

---

## 10. 最小检查

至少检查：

- 三份 Context 都引用 `intent_rev=1 / state_rev=1 / brief-001 rev=1`；
- Context 没有把 BKP 写成原创事实；
- Context 没有把未决定的谜底写成 Canon；
- 任何“林晚其实活着”等推断都只能是候选，不得当事实；
- `story_state.yaml` SHA/内容未被本任务改变；
- 没有修改 KnowledgeRetrieve（除非事先确认了阻塞性 bug）；
- 没有进入 G4-D。

如果方便，可用小脚本做机械检查；不要为了这一步设计通用框架。

---

## 11. Git 提交

只添加本任务明确产物，例如：

- `.../g4c/retrieval/*`
- `.../g4c/contexts/*`
- `.../g4c/G4C_VALIDATION.md`

不要提交无关 dirty/untracked。

建议 commit：

`test: validate G4-C minimal context synthesis`

push 前再次：

```bash
git status --short
git diff --cached --stat
git diff --cached
```

确认没有无关文件后再 commit/push。

---

## 12. 最终回报格式

完成后只报告：

1. KnowledgeRetrieve 是否真实跑通，两本 BKP 是否正常加载；
2. Q1/Q2/Q3 各自 Retrieval 状态和最终选中 Hit 数；
3. 三份 Context 的文件路径；
4. 是否存在真实跨书互补/冲突；
5. 是否存在 BKP gap / Retrieval 阻塞；
6. 权威 Story State 是否保持未修改；
7. 修改文件清单；
8. 测试/检查结果；
9. commit SHA；
10. 最终 `git status --short`；
11. 结论：`G4-C 技术验证完成候选` 或 `G4-C 未通过`，不要自动进入 G4-D。