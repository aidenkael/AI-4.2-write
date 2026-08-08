# B09 原著蒸馏 Benchmark 执行协议 v0.1

> 日期：2026-08-09
> 状态：第一轮可执行协议
> 依赖：`00_项目控制/AI写作Skill_Benchmark设计_v0.1.md`
> 边界：不上传第三方原著正文；原文只在 `01_原始素材` 本地只读使用。

## 1. 本轮目标

B09 第一轮不评“谁最会写书评”，而评四件事：

1. 能否把原著事实与解释分开；
2. 能否用可定位证据支撑重要结论；
3. 能否把作品特征转成跨作品可复用机制，而不是换名仿写；
4. 能否诚实说明覆盖范围、反例、置信度和不适用条件。

第一轮只验证方法，不建设正式 `02_原著蒸馏` 体系。通过 Benchmark 后再决定哪些结构进入正式蒸馏层。

## 2. 实验角色分工

- **Benchmark Controller**：固定样本、统一输入输出、匿名化、汇总结果；不得参与参赛方案自评。
- **Runner D0 / A / B / C**：彼此隔离执行，不读取其他 Runner 输出。
- **Judge 1 / Judge 2**：匿名盲审，只看到随机标签；必须给证据和失败类型，不给单一“9.x 分”。
- **Human Review**：只做成对排序与创作价值判断，不承担大规模事实核对。

如果当前环境无法真正并行 spawn 独立 Agent，可由本地 Codex/Claude/其他 Agent 分四次独立会话执行；每次必须新会话，不读取前一方案产物。

## 3. 第一轮样本

总计 3 部作品：

- `WN-A`：代表持续阅读驱动力、商业连载、期待—兑现循环的网络小说；
- `WN-B`：代表人物关系、复杂角色或情绪推进能力较强的网络小说；
- `WL-A`：代表人物心理、文学表达、内心矛盾或叙述距离的世界文学作品。

样本必须来自当前本地合法持有的 `01_原始素材`。若 Controller 无法直接看到本地文件清单，由本地执行 Agent 根据已有素材索引选书，并把“为什么选这本”写入 manifest；不得为了迎合某个参赛方案而挑样本。

### 3.1 每部作品固定两个窗口

优先按章节边界冻结：

- `OPENING`：正文最早连续 6 章；
- `MIDDLE`：以全书章节总数中点为中心，连续 6 章。

目的：同时测试开篇机制和中段漂移，避免把“黄金三章特征”错误外推成整本规律。

若作品章节不足 12 章，或章节边界不可靠：

- 按稳定字符范围切为约 8,000–12,000 字符的 segment；
- 冻结一个开篇 segment 和一个中段 segment；
- manifest 必须标记 `boundary_mode: segment`，不得声称章级覆盖。

### 3.2 冻结原则

每个样本必须记录：

- source kind；
- title（允许本地 manifest 保存，公开汇总可匿名）；
- source path；
- SHA256；
- byte size；
- encoding；
- chapter/segment 边界；
- 被选中的两个窗口；
- coverage = sampled；
- 未覆盖范围声明。

**不复制正文。** Runner 根据 manifest 直接只读原文件相应范围。

## 4. 四个参赛方案

### D0 — Minimal Baseline

同模型、同窗口，只给最小任务：

> 分析这段小说材料中最值得学习、可迁移到原创长篇小说的写作机制。区分原文事实、你的解释和可复用方法；不要大量复述原文。

作用：判断复杂 Skill 是否真的比无 Skill 基线增加价值。

### A — oh-story Deconstruction Adaptation

上游：`worldwonderer/oh-story-claudecode`，MIT。

只借其“长篇拆文”方法，不照搬其输出目录。核心测试要点：

- 开篇/逐章情节点；
- 角色与设定归纳；
- 关键信息推进；
- 节奏、爽点、期待点、情绪触动点；
- 读者需求与情绪引擎；
- 可复现模块卡；
- 文风、对白、章首/章末等写法公式。

A 必须遵守本 Benchmark 的统一 Evidence / Interpretation / Mechanism 输出合同，不能因为上游原版格式更长而获得长度优势。

### B — ani-book Evidence-first Analysis

上游：`ExplosiveCoderflome/ani-book-skill`，Apache-2.0。

核心测试要点：

- 先冻结 source scope / fingerprint；
- bounded segment notes；
- 低推断事实笔记先行；
- fact / inference / hypothesis 分离；
- confidence / counterevidence；
- 章级、阶段级、全书级尺度明确区分；
- mechanism card 包含必要前提、读者回报、失败方式、反例/边界和安全改造方向；
- sampled coverage 不得冒充 full coverage。

### C — AI-write Candidate v0.1

不是“我们默认更强”的方案，而是待证伪候选。它组合三条原则：

1. **Evidence-first**：先证据，再解释，再机制；
2. **Reader-causality**：机制必须解释“作者做了什么 → 读者经历了什么 → 为什么形成期待/情绪/认知变化”；
3. **Transfer test ready**：每张机制卡必须能被拿到另一部原创故事中测试，而不是只描述原作。

C 不允许引用 A/B 的本轮输出；只允许读取同一冻结原文窗口和本协议。

## 5. 统一输出合同

每个 Runner 每部作品只输出以下四类文件，文件名一致：

```text
runner-output/
├── 01_evidence_notes.md
├── 02_interpretation.md
├── 03_mechanism_cards.md
└── 04_self_limits.md
```

### 5.1 Evidence Notes

每条使用稳定 ID：

```text
EVID-001
范围：OPENING / 第X章 / segment-xxx
事实：只描述文本明确发生的内容
短证据：必要时仅保留极短摘录，不复制长段原文
关联：人物 / 情节 / 对话 / 情绪 / 节奏 / 信息 / 设定 / 意象
```

禁止在 Evidence Notes 中写“作者想表达”“读者一定会”“这证明了”等高推断句。

### 5.2 Interpretation

```text
CLAIM-001
类型：inference / hypothesis
结论：
支持证据：EVID-xxx, EVID-xxx
反证/边界：
适用范围：OPENING / MIDDLE / 两者
置信度：high / medium / low
```

强结论优先要求至少两个独立证据锚点。单一锚点只能缩小范围或降低置信度。

### 5.3 Mechanism Card

每张卡统一包含：

```text
PATTERN-001｜机制名称
解决的问题：
必要前提：
作者侧动作：
读者侧经历：
中间因果链：
为什么有效：
失败模式：
反例/边界：
适用题材/阶段：
不适用场景：
安全迁移方式：
不可照搬元素：
证据来源：CLAIM-xxx / EVID-xxx
迁移测试命题：给一个与原作题材不同的新故事，说明怎样验证该机制仍有效
```

### 5.4 Self Limits

必须明确：

- 本轮只读了哪些窗口；
- 哪些整书结论不能下；
- 哪些判断需要补读其他章节；
- 哪些机制可能只是这本书/这一阶段的特例；
- 哪些输出有复述或模仿风险。

## 6. 第一轮评分维度

不计算一个“总分 9.2”。保留逐维结果与成对排序。

### 6.1 可确定检查

1. `coverage_honesty`：是否把 sampled 写成 full；
2. `evidence_anchor_rate`：重要 CLAIM 有证据锚点的比例；
3. `unsupported_claim_count`：无支持锚点的重要结论数；
4. `fact_inference_leak_count`：事实层混入推断的次数；
5. `counterevidence_presence`：强规律是否主动检查反例；
6. `mechanism_contract_complete`：机制卡字段完整性；
7. `source_copy_risk`：是否出现不必要的大段复述/摘抄；
8. `cross_scale_confusion`：开篇规律是否被冒充整书规律。

### 6.2 Judge 盲审

Judge 对匿名方案逐项给 `PASS / WARN / FAIL`，并提供 evidence：

- 事实可信度；
- 推断克制；
- 因果解释；
- 读者体验解释；
- 机制可操作性；
- 迁移距离；
- 反例意识；
- 是否只是剧情摘要；
- 是否只是“节奏紧凑/人物鲜明”类空话；
- 是否存在模板化过拟合。

### 6.3 人工盲评

人工每次只做成对选择：

- 哪一份更能帮助我以后原创，而不是理解原书？
- 哪一张机制卡最想拿去新故事中试？
- 哪一份最像“看起来专业但实际没法用”？

不得向人工展示 Runner 身份。

## 7. 通过门槛

某方案只有同时满足以下条件，才有资格进入第二轮：

- 没有明显 coverage 欺骗；
- 事实层与解释层基本分离；
- 主要结论大多数可追溯；
- 机制卡不是桥段换名；
- 至少在 2/3 作品上表现稳定；
- 人工成对盲评没有明显落后 Baseline；
- token/上下文成本没有失控。

某个上游只在一个局部维度胜出，可以只吸收该能力，不要求整套引入。

## 8. 第二轮触发条件

第一轮结束后才做：

1. 选出每个维度冠军；
2. 将冠军机制用于一个与原作题材不同的原创小场景；
3. 进行迁移 A/B 测试；
4. 只有迁移后仍有效的机制，才进入 `04_写作知识库` 候选；
5. 具体作品分析留在 `02_原著蒸馏`，跨作品方法进入 `04_写作知识库`。

## 9. 上游引用与许可证

- oh-story-claudecode: MIT，Benchmark 中只做方法适配并保留来源说明。
- ani-book-skill: Apache-2.0，Benchmark 中只做方法适配并保留来源说明。
- 其他许可证未核清、AGPL、NC 类来源不得在本轮直接复制为 AI-write 生产 Skill；可作为架构/Benchmark 参考。

## 10. 本轮完成定义

B09 第一轮只有在以下工件全部存在时才算完成：

- 3 个 source manifest；
- 4 Runner × 3 works = 12 组标准化输出；
- 匿名映射（仅 Controller 可见）；
- 至少 2 份独立 Judge 结果；
- 程序检查结果；
- 人工成对盲评记录；
- 第一轮结论：直接采用 / 二次改造 / 仅 Benchmark / 淘汰。
