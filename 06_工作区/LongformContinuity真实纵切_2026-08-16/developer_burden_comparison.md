# Developer Burden Comparison｜开发者负担第二次测量

> 状态：FROZEN（2026-08-16）。
> 判定：**DEVELOPER_OR_AUTHOR_BURDEN_GAP = REPEATED**（重复出现，非一次性实验成本）。

## 1. 逐环节对比

| 环节 | 第一轮（StoryWrite） | 第二轮（本场） | 性质 |
| --- | --- | --- | --- |
| Brief | 手工撰写 writing_brief + creation_brief.json | 同左，结构完全重复 | 重复机械（半创作半机械） |
| **State settlement** | 不适用（种子态，无前场正文） | **新增环节**：手工提取 mechanical/ambiguous/creative，手工构造 shadow_state JSON | 重复机械（每场必有；本轮为纯手工） |
| State 版本与 authority | 人工判断 rev1/rev2 + simulation gate | 人工构造 shadow rev3 + 再开 simulation gate + 手写三重 metadata | 重复且易错 |
| Context selection | 9 条逐条 reason | 13 条选中 + 9 条未选理由 | 后台智能判断，逐场重复 |
| Context compile | 手写一次性脚本并运行 | 复制改写一次性脚本并运行 | 重复机械 |
| recent prose selection | 不适用（第一场） | **新增环节**：手工截取 W1 末段约 1400 字并定位权威 | 重复机械（每场必有） |
| W0 | 创作核心 | 创作核心 | 创作（作者只读结果） |
| Review | 手工五立场记录 | 手工五立场 + 7 项连续性专项 | 后台判断，逐场重复 |
| W1 | 修订记录 + 全文 | 同左 | 创作核心 |
| 归档 | postmortem / report | 同左 + 负担对比 | 重复机械 |

## 2. 与第一轮结论的关系

- 第一轮记录的"后台逐场手工操作负担"在本轮**逐项复现**（Brief / selection / compile / review 归档），判定 **REPEATED**，不是 ONE_OFF_EXPERIMENT_COST。
- 本轮还**新增**了两个第一轮不存在的重复环节：State settlement 与 recent prose selection。它们随场次线性增长：第 N 场就要做 N-1 次结算 + N-1 次 recent prose 截取。
- 作者认知负担仍为低：全流程不要求作者理解 state id / Context / shadow authority / selection；作者应做的仍是三件事（说要写什么、读正文、给反馈）。

## 3. 负担排序（两轮合并证据）

1. **State settlement（本轮最重）**：读正文 → 分类 mechanical/ambiguous/creative → 构 State JSON → 保证 schema 与 authority 合规。纯机械但需要纪律，是最容易出错、也最值得辅助的环节。
2. **Brief 编译 + selection**：一句话意图 → creation_brief 字段 → 逐条 selection reason。与第一轮相同。
3. **recent prose 窗口维护**：截取、定位权威、附元数据。轻，但每场必做。
4. **一次性编译脚本**：每场复制改写。轻，但每场必做。

## 4. 对开发决策的输入

- 两个候选都获得了"第二次重复"的证据：
  - `THIN_STORYWRITE_ENTRY`（一句话 → Brief → selection → compile → recent prose 的薄流程入口）；
  - `MECHANICAL_SETTLEMENT_ASSIST`（accepted prose → mechanical 提取 → state update 的薄辅助）。
- 本轮证据显示 **settlement 的重复增速更高**（场次线性且易错），但两者都满足"重复机械动作"特征；最终 BUILD 判断与优先序见 final_report Q20–Q24。
- 按合同：只记录 BUILD_CANDIDATE，**本轮不开发**。
