# B09 原著蒸馏 Benchmark Runner Pack

> 这是执行包，不是正式生产 Skill。
> 总协议见：`00_项目控制/B09_原著蒸馏Benchmark_执行协议_v0.1.md`
> 本地运行数据统一放在 `06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/`，已 gitignore。

## 1. 实验纪律

四个 Runner 必须满足：

- 同一模型；
- 同一模型参数；
- 同一 source manifest；
- 同一 OPENING / MIDDLE 窗口；
- 同一最大输出预算；
- 独立新会话；
- 不读取其他 Runner 输出；
- 不读取 Judge 结果；
- 不扩展 manifest 之外的原著范围；
- 原著只读，不复制到 GitHub。

若模型平台不暴露 temperature / seed 等字段，在 `run_metadata.json` 标记 `unavailable`，不得捏造。

## 2. 本地目录

建议：

```text
06_工作区/01_待处理/B09_原著蒸馏Benchmark/
├── _local_manifests/
│   ├── WN-A.json
│   ├── WN-B.json
│   └── WL-A.json
└── _local_runs/
    └── round-01/
        ├── WN-A/
        │   ├── D0/
        │   ├── A/
        │   ├── B/
        │   └── C/
        ├── WN-B/
        └── WL-A/
```

每个 Runner 目录必须有：

```text
01_evidence_notes.md
02_interpretation.md
03_mechanism_cards.md
04_self_limits.md
run_metadata.json
```

## 3. Controller 前置检查

执行前：

1. 读取 manifest；
2. 对 source 重新计算 SHA256，必须等于 manifest；
3. 只读取 `coverage.windows.OPENING` 和 `coverage.windows.MIDDLE` 的字符范围；
4. 将两个窗口分别标注为 `OPENING` / `MIDDLE` 后交给 Runner；
5. 不提供作品在其他系统中的旧分析结果；
6. 不告诉 Runner 其他参赛方案是谁。

## 4. 所有 Runner 共用的强制输出合同

无论方法如何，最终都必须生成四个文件。

### `01_evidence_notes.md`

只允许低推断事实。格式：

```text
# Evidence Notes

## EVID-001
- 范围：OPENING / MIDDLE / 具体章或 segment
- 事实：
- 短证据：
- 关联：人物 / 情节 / 对话 / 情绪 / 节奏 / 信息 / 设定 / 意象
```

Evidence 层禁止把“作者意图”“读者一定会怎样”“这说明……”写成事实。

### `02_interpretation.md`

```text
# Interpretation

## CLAIM-001
- 类型：inference / hypothesis
- 结论：
- 支持证据：EVID-001, EVID-00x
- 反证/边界：
- 适用范围：OPENING / MIDDLE / 两者
- 置信度：high / medium / low
```

### `03_mechanism_cards.md`

```text
# Mechanism Cards

## PATTERN-001｜机制名称
- 解决的问题：
- 必要前提：
- 作者侧动作：
- 读者侧经历：
- 中间因果链：
- 为什么有效：
- 失败模式：
- 反例/边界：
- 适用题材/阶段：
- 不适用场景：
- 安全迁移方式：
- 不可照搬元素：
- 证据来源：CLAIM-xxx / EVID-xxx
- 迁移测试命题：
```

### `04_self_limits.md`

必须说明：

- coverage = sampled；
- 只读了哪些窗口；
- 哪些整书结论不能下；
- 哪些判断需要补读；
- 哪些机制可能只是局部特例；
- 哪些内容存在复述/模仿风险。

---

# 5. Runner D0 — Minimal Baseline

除共用输出合同外，只给下面这段任务，不加载任何小说分析 Skill：

```text
你正在参加一个盲测。请分析提供的两个冻结小说窗口中，最值得迁移到原创长篇小说的写作机制。

要求：
1. 严格区分原文事实、你的解释和可复用方法。
2. 所有重要结论尽量给可定位的证据锚点。
3. 不大量复述原文，不模仿原作，不输出换名桥段。
4. 只能对本次 OPENING 和 MIDDLE 样本负责，不能声称看过整本书。
5. 按统一四文件合同输出。
```

D0 的意义是测“复杂方法是否真的优于一个合理的普通提示”。

---

# 6. Runner A — oh-story Method Adaptation

方法来源：`worldwonderer/oh-story-claudecode` 的 `story-long-analyze`，MIT。

除共用输出合同外，执行下面的方法约束：

```text
你是网络小说结构分析师，但当前任务是 Benchmark，不是生成普通书评。

对 OPENING 与 MIDDLE 分别进行拆解，再跨窗口聚合。重点寻找：

A. 章/场景推进
- 关键情节点；
- 目标、阻碍、转折、结果；
- 章首如何建立期待；
- 章末如何形成继续阅读压力。

B. 信息与节奏
- 关键信息如何被提出、延迟、扩写、确认或反转；
- 爽点/期待点/紧张点/情绪触动点的铺垫→释放→余波；
- 小循环、中循环的结构；
- OPENING 与 MIDDLE 是否发生节奏/打法漂移。

C. 人物与关系
- 主角与关键角色的功能；
- 角色目标、关系变化和冲突来源；
- 哪些人物设计服务持续追读。

D. 可复现模块
- 读者需求是什么；
- 作品用什么“情绪引擎/期待引擎”满足它；
- 把有效模式抽象成机制卡，而不是桥段模板。

E. 写法
- POV、对白、场景组织、信息释放、句段节奏、章首/章末；
- 只有在样本能支持时才下结论。

必须额外执行两条防过拟合检查：
1. OPENING 中出现的规律，必须检查 MIDDLE 是否仍成立；不成立就标记阶段性规律。
2. 不能因为一个爆点存在，就推断全书“每章都有同类爆点”。

最终仍按 Benchmark 的 Evidence → Interpretation → Mechanism Card 四文件合同输出。
```

注意：不要把 oh-story 原有的大型目录结构、原文备份、全书逐章处理要求带入本轮，因为所有 Runner 的覆盖范围必须完全一致。

---

# 7. Runner B — ani-book Evidence-first Method

方法来源：`ExplosiveCoderflome/ani-book-skill` 的 reference analysis，Apache-2.0。

除共用输出合同外，执行：

```text
你执行 evidence-first reference analysis。

第一原则：先产生低推断 segment notes，再做综合。不要从第一印象直接跳到“整书规律”。

步骤：

1. Scope check
- 确认 source fingerprint 与 manifest 一致；
- coverage 只能是 sampled；
- 明确 OPENING / MIDDLE 是两个有限窗口。

2. Low-inference notes
对两个窗口分别提取：
- 剧情节点与状态变化；
- 人物目标、行动、结果；
- 关系变化；
- 世界规则/资源/限制；
- 情绪、意象和叙事技法信号；
- 钩子、回报、潜在流失点；
- 必要的短证据锚点。
此阶段不得断言整书主题、隐藏作者意图或确定商业结论。

3. Cross-scale synthesis
明确区分：
- 当前章/segment 能证明什么；
- OPENING 阶段能证明什么；
- MIDDLE 阶段能证明什么；
- 只有两个窗口时，哪些全书结论仍然 open。

4. Claim contract
每个重要结论标记：
- fact / inference / hypothesis；
- high / medium / low；
- source refs；
- counterevidence；
- supported / contested / open。

5. Pattern cards
机制卡必须包含：必要前提、运行机制、读者回报、失败方式、反例/边界、安全改造方向和不可照搬元素。

强规律若只有一个证据锚点，必须降低置信度或缩小适用范围。
```

最终转换到统一四文件合同，不额外增加 B 独有文件，以避免输出长度造成评审偏差。

---

# 8. Runner C — AI-write Candidate v0.1

C 是待证伪候选，不享有任何“自家方案”优待。

```text
你的任务不是解释这本书“讲了什么”，而是建立可被原创写作测试的因果机制。

按三层执行：

第一层：Evidence-first
- 只写可定位事实；
- 把观察与解释分开；
- 找不符合规律的证据，而不只找支持证据。

第二层：Reader-causality
对每个候选机制追问：
- 作者具体控制了什么信息、行动、关系、场景或语言条件？
- 读者在这一刻已经知道什么、想知道什么、误以为什么？
- 读者的期待/情绪/人物判断发生了什么变化？
- 哪一步是因，哪一步只是伴随现象？
- 如果删除这个设计，阅读体验具体损失什么？

优先建立这样的链条：
作者侧操作 → 角色/场景状态变化 → 读者感知/解释 → 期待或情绪变化 → 后续选择/翻页压力 → 兑现或修正。

第三层：Transfer-test-ready
每张机制卡必须回答：
- 换成完全不同题材，还保留什么抽象关系？
- 哪些原作专名、设定、桥段必须丢弃？
- 最小可迁移单元是什么？
- 怎样设计一个新故事 A/B 测试，证明它不是只在原作有效？

专项观察：

网络小说：
- 阅读驱动力、期待债、阶段回报、信息释放、章末压力、升级台阶、主角代理权。

世界文学：
- 人物自我解释与真实行动是否冲突；
- POV 选择性注意；
- 叙述距离；
- 潜台词；
- 意象是否承担关系/主题/状态变化，而非只是漂亮描写。

禁止：
- “节奏紧凑、人物鲜明、代入感强”而没有因果解释；
- 把频率误当因果；
- 把身体动作词库当情绪机制；
- 把一个桥段改名后叫“可复用模板”；
- 用 OPENING 的发现替整书下结论。
```

最终按统一四文件合同输出。

---

# 9. run_metadata.json

每次运行记录：

```json
{
  "benchmark": "B09_original_work_distillation",
  "round": 1,
  "sample_id": "WN-A",
  "runner": "A",
  "model": "<exact model name>",
  "provider": "<provider or unavailable>",
  "temperature": "<number or unavailable>",
  "seed": "<number or unavailable>",
  "started_at": "<ISO-8601>",
  "finished_at": "<ISO-8601>",
  "input_manifest_sha256": "<manifest hash>",
  "source_sha256_verified": true,
  "scope_expanded": false,
  "other_runner_outputs_read": false,
  "notes": ""
}
```

模型版本不同的运行不能直接合并成同一轮 Skill 对比。

# 10. 完成后

四个 Runner 全部结束后，不立即看身份比较。先运行程序检查，再做匿名化，然后交给两个 Judge 和人工成对盲评。
