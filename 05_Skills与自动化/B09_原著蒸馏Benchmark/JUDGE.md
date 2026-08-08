# B09 原著蒸馏 Benchmark — Blind Judge Protocol

> Judge 不得读取 `_controller/blind_map.json`、Runner 身份、run_metadata 或其他参赛方案说明。
> Judge 只看 `_blind/<sample>/` 下的匿名 Runner 输出，以及该 sample 共用的 `_source/` 冻结输入包。

## 0. Judge 可见输入边界

每个 sample 的 `_source/` 包含同一份：

- `OPENING.txt`
- `MIDDLE.txt`
- `manifest_info.json`

这些冻结窗口只用于核验匿名方案是否忠实引用、是否曲解文本、是否把窗口外知识带入 Claim。

硬性限制：

- 只能使用 `_source/` 中的冻结窗口核证；
- 不得搜索原著全文；
- 不得根据自己记忆补充窗口外剧情；
- 不得因为知道作品后续内容，就惩罚一个只对 sampled 窗口负责的 Runner；
- 若窗口自然截断场景，只能检查 Runner 是否诚实处理不确定性。

## 1. Judge 的任务

你不是来判断“哪份写得更漂亮”，而是判断哪份分析：

- 更可信；
- 更克制；
- 更能解释因果；
- 更能把原作经验转成原创可验证机制；
- 更少把剧情摘要、标签或漂亮术语冒充方法论。

不要使用单一 10 分制。每个维度给 `PASS / WARN / FAIL`，再进行匿名方案成对排序。

## 2. 强制审查维度

### J01｜Coverage honesty

检查：

- 是否明确只读 OPENING / MIDDLE；
- 是否把 sampled 冒充 full；
- 是否用“全书一直如此”“作者整本书都……”等超范围结论。

判定：

- PASS：范围边界清楚，结论主动限缩；
- WARN：偶尔有范围模糊，但 Self Limits 能纠正；
- FAIL：明显把样本外推成整书真理。

### J02｜Evidence fidelity

必须把 Evidence Notes 与该 sample 的 `_source/OPENING.txt`、`_source/MIDDLE.txt` 对照。

检查：

- Evidence 所述事件、状态、台词或叙事信号是否确实出现在对应窗口；
- 短证据是否与事实描述一致；
- Evidence 是否把窗口外剧情、模型记忆或猜测伪装成文本事实；
- Evidence ID 与后续 Claim 虽然形式上有关联，但实际语义是否支持该 Claim。

重点找：

- 把动机猜测写成事实；
- 把读者感受写成事实；
- 把作者意图写成事实；
- 证据锚点与 Claim 实际无关；
- 引用片段存在，但被过度解释；
- 窗口中根本不存在的事实。

### J03｜Inference discipline

检查：

- inference / hypothesis 是否分开；
- 置信度是否与证据量相称；
- 强结论是否主动寻找反证；
- 不确定时是否敢于写 open，而不是凑结论。

### J04｜Causal explanation

高质量机制必须回答：

> 作者做了什么 → 角色/信息/场景发生什么变化 → 读者感知/判断/期待如何变化 → 为什么产生阅读效果。

FAIL 典型：

- “节奏快，所以好看”；
- “人物立体，所以有代入感”；
- “用了伏笔，所以读者想继续看”；
- 只列特征，不解释中间因果。

### J05｜Reader-model quality

检查是否真正说明读者在不同时间点：

- 已知什么；
- 不知道什么；
- 想知道什么；
- 误判什么；
- 得到什么阶段性回报；
- 为什么愿意继续投入。

不要因为方案频繁使用“读者”二字就判好；必须有文本证据和因果。

### J06｜Mechanism transferability

检查机制卡能否脱离原作专名继续成立。

PASS 倾向：

- 明确前提；
- 明确最小可迁移结构；
- 说明换题材时保留什么、重做什么；
- 给出可验证迁移命题。

FAIL 倾向：

- 把“主角被某人羞辱后打脸”换几个名词叫模板；
- 依赖原作独占设定才成立；
- 直接指导模仿原作桥段或文风。

### J07｜Counterexample awareness

检查：

- 是否找 OPENING 与 MIDDLE 的差异；
- 是否发现同一规律的例外；
- 是否因反例而调整置信度/适用范围。

“完全没有反例”通常需要非常强的证据，不应轻易接受。

### J08｜Actionability for an author

问：

> 一个真实作者拿到这张机制卡，下一次设计原创剧情时，是否知道该设计哪些条件和检查什么结果？

若只能增加理解、不能指导设计或诊断，则最多 WARN。

### J09｜Summary masquerading as analysis

检查是否大量篇幅只是：

- 发生了什么；
- 谁做了什么；
- 角色关系是什么；

而没有进一步形成证据支持的机制。

剧情摘要本身可以是 Evidence，但不能冒充最终蒸馏成果。

### J10｜Template / pseudo-rigor risk

检查：

- 是否机械填满所有字段；
- 是否出现大量无证据的固定频率、固定次数、固定比例；
- 是否用“黄金公式”“每 N 章必须”等口径制造伪精确；
- 是否为了显得严谨而重复同一结论。

### J11｜Source-copy / imitation risk

检查：

- 是否保留不必要的长原文；
- 是否过密复述情节；
- 是否把标志性桥段包装成“安全迁移”；
- 是否鼓励克隆作者文风。

### J12｜Compression quality

更长不等于更好。

检查：

- 同一个机制是否重复三四次；
- 是否可以删掉 30% 文字而不损失实质；
- 信息密度是否足以支撑未来进入知识库。

## 3. 每个匿名方案的输出格式

对每个 sample / label 输出：

```text
# Judge Review｜<sample>｜<anonymous-label>

## Verdict matrix
- J01 Coverage honesty: PASS/WARN/FAIL
- J02 Evidence fidelity: PASS/WARN/FAIL
- J03 Inference discipline: PASS/WARN/FAIL
- J04 Causal explanation: PASS/WARN/FAIL
- J05 Reader-model quality: PASS/WARN/FAIL
- J06 Mechanism transferability: PASS/WARN/FAIL
- J07 Counterexample awareness: PASS/WARN/FAIL
- J08 Actionability: PASS/WARN/FAIL
- J09 Summary masquerading risk: PASS/WARN/FAIL
- J10 Template/pseudo-rigor risk: PASS/WARN/FAIL
- J11 Source-copy/imitation risk: PASS/WARN/FAIL
- J12 Compression quality: PASS/WARN/FAIL

## S1/S2 findings
每条包含：
- severity: S1 / S2
- dimension:
- location:
- evidence:
- issue:
- why_it_matters:

## Strengths
只列有具体证据的优势。

## Most useful mechanism card
- pattern:
- why:
- what would need human verification:

## Most suspicious mechanism card
- pattern:
- why:

## Overall
- reliable_claims:
- questionable_claims:
- transfer_readiness: ready / needs_revision / benchmark_only
```

S1：足以使该方案不应进入下一轮的根本问题，如系统性无证据推断、范围欺骗、仿写风险。
S2：明显降低方法价值，但可以局部修复。

## 4. 同一 sample 的成对排序

完成四个匿名方案单独审查后，再做：

```text
Evidence reliability:
1. <label>
2. <label>
3. <label>
4. <label>

Mechanism transferability:
1. ...

Author usefulness:
1. ...

Least pseudo-rigorous:
1. ...

Overall pairwise preference:
<label> > <label> > <label> > <label>
```

必须给每个排序一个简短理由；不能根据长度排序。

## 5. 跨作品稳定性

Judge 完成三个 sample 后，再额外判断：

- 哪个匿名方法似乎只擅长网文；
- 哪个只擅长文学分析；
- 哪个在三本作品上都能维持证据纪律；
- 哪个产生的机制卡跨题材最稳定；
- 哪个最容易模板化；
- 哪些维度应该拆开选冠军，而不是选一个总冠军。

在揭盲之前不要猜测 Runner 身份。

## 6. 两个 Judge 的独立性

Judge-1 与 Judge-2 必须使用两个全新、彼此不共享历史的独立进程/会话。

若两者使用同一模型：

- 两个 Judge 的 sample 顺序应独立随机；
- 每个 sample 内四个匿名 label 的呈现顺序也应独立随机；
- Judge-2 不得读取 Judge-1 结果；
- 不因两份结果高度相似就自动视为“共识”，仍需人工检查争议项目。

模型多样性不是本轮硬门槛；真正的人类盲评仍是主观创作价值的最终补充层。

## 7. Judge 禁止事项

- 不给“综合 9.3 分”；
- 不因为格式整齐就默认更专业；
- 不因为某方案术语更多就给高评价；
- 不因为和自己文学观点一致就忽略证据不足；
- 不尝试识别 Runner 身份；
- 不修改参赛输出；
- 不读取冻结 `_source/` 之外的原著范围补证据。
