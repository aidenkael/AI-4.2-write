# BookDistill Observer Contract v0.1

> 角色：BookDistill 的后台发现层合同。它不是作者面对的新产品入口，也不是新的长期知识协议。

## 目标

让不同观察能力**直接读取 SourcePrepare 的同一份原著**，各自形成可追溯的作品内发现，再由 BookDistill 统一核证、去重、合并和收敛。

固定的是职责边界，不固定模型、Agent 数量或调用次数。

## 前置：BookProfile Scout

深度 Discovery 前先运行一个轻量的导航性识别：`book_profile_scout.md` + `profile_scout.py`。

它只建立 `book_profile_initial.md`：作品定位、Contract/Reader Promise、粗略阶段、显著/潜在强项和不确定项的**假设**。它不算完整蒸馏，也没有权力排除后续观察维度；两个默认观察者仍直接读原著。

## 输入

只接受 SourcePrepare `PASS` 包：

`06_工作区/SourcePrepare/<book_id>_<书名>/`

正文来源只有：

- `chapters/NNNN.md`
- 必要时 `full.md` 用于跨章定位

观察者不得把另一个观察者的摘要当作原著替代物。

## 默认观察者

1. `longform_reader_dynamics`：长篇运行 / 读者动力
2. `reader_page_craft`：Reader / Page Craft

两者是默认互补镜头，不是永久冻结的唯一镜头。作品有明确特殊价值时可以增加新的观察者或进入 Developmental Deep Dive。

## Staging 输出

`observer_bridge.py init` 生成：

```text
<bookdistill_output>/
└── discovery/
    ├── longform_reader_dynamics/
    │   ├── observer_manifest.json
    │   ├── chapters/ch_NNNN.md
    │   └── synthesis.md
    └── reader_page_craft/
        ├── observer_manifest.json
        ├── chapters/ch_NNNN.md
        └── synthesis.md
```

这些是**发现阶段 staging**，不是 BKP，不自动成为写作规则。

`discovery/` 是逐章工作底稿，默认 Local Only；`.gitignore` 已排除 `02_原著蒸馏/*/discovery/`。正式长期保存的是 BookDistill 收敛后的 canonical evidence、BookProfile、Deep Dive 结论和 BKP，不把 observer staging 当长期知识库提交。

## 可桥接条目

观察者只直接产出三类：

- `OBSERVATION`：作品内可观察到的创作现象/效果；
- `INFERENCE`：由原文支持、但不是字面事实的解释；
- `BOUNDARY`：边界、反例、译本/样本限制、不确定性。

观察者**不要直接产出 `MECHANISM`**。是否抽象成可迁移机制由 BookDistill 总编辑层决定。

格式：

```text
- [OBSERVATION] dimension:<维度> | observer:<observer_id> | <一句话观察>｜证据：chapters/NNNN.md#Lx-Ly｜置信度：高/中/低
- [INFERENCE] observer:<observer_id> | <推断>｜证据：chapters/NNNN.md#Lx-Ly｜置信度：高/中/低
- [BOUNDARY] observer:<observer_id> | <边界/反例>｜证据：chapters/NNNN.md#Lx-Ly｜置信度：高/中/低
```

规则：

- `OBSERVATION` 必须有 `dimension`；
- 每条必须有 `observer:<observer_id>`；
- chapter staging 文件只引用同章原文；
- 跨章组合效果放在 `synthesis.md`，并列出多个章节证据，由 BookDistill 再收敛；
- 没有信号就留空，不以数量充当质量；
- 不大量摘抄原文。

## 运行顺序

执行多视角 Discovery 前，运行 BookDistill 的 Agent 必须先读本文件，再读 Scout 与对应观察者合同。

```bash
python 05_Skills与自动化/01_Skills/BookDistill/scripts/book_distill.py validate --input <SP_PASS>
python 05_Skills与自动化/01_Skills/BookDistill/scripts/book_distill.py prepare --input <SP_PASS> --output <BD_OUT>

# 先识别 / 导航：不做完整蒸馏，不过滤后续发现
python 05_Skills与自动化/01_Skills/BookDistill/scripts/profile_scout.py init \
  --input <SP_PASS> --output <BD_OUT>

# Agent 按 observers/book_profile_scout.md 直接读取锚点原著并填写 book_profile_initial.md
python 05_Skills与自动化/01_Skills/BookDistill/scripts/profile_scout.py validate \
  --input <SP_PASS> --output <BD_OUT>

# 再建立两个完整 Discovery staging
python 05_Skills与自动化/01_Skills/BookDistill/scripts/observer_bridge.py init \
  --input <SP_PASS> --output <BD_OUT>
```

然后 Agent 分别读取：

- `observers/longform_reader_dynamics.md`
- `observers/reader_page_craft.md`

并直接阅读原著，填写各自 `discovery/.../chapters/` 与 `synthesis.md`。

完成后：

```bash
python 05_Skills与自动化/01_Skills/BookDistill/scripts/observer_bridge.py validate \
  --input <SP_PASS> --output <BD_OUT> --observer longform_reader_dynamics

python 05_Skills与自动化/01_Skills/BookDistill/scripts/observer_bridge.py validate \
  --input <SP_PASS> --output <BD_OUT> --observer reader_page_craft

python 05_Skills与自动化/01_Skills/BookDistill/scripts/observer_bridge.py merge \
  --input <SP_PASS> --output <BD_OUT>
```

桥接脚本只做确定性校验与无覆盖合并：

- 校验 SourcePrepare snapshot；
- 校验证据引用、行号、observer 标签、dimension；
- 拒绝跨章错引；
- 幂等合并到 BookDistill canonical `evidence/ch_NNNN.md`；
- 不处理 `synthesis.md` 的文学判断；
- 不自动提升为 `MECHANISM`、Pattern 或 BKP。

之后继续现有 BookDistill：

`assemble → final profile → 必要 deepdive → 总编辑收敛 → bkp`

最终 `book_profile.md` 需要回看 `book_profile_initial.md`，至少说明：`confirmed / revised / rejected / newly_discovered`。Scout 没看到、后续才发现的重要价值属于正常结果。

## 总编辑合并原则

BookDistill 读取两个观察者的 staging + canonical evidence 时：

1. 同义发现合并，不按 observer 数量投票；
2. 冲突保留并回原著核证；
3. 一个观察者没看见，不等于另一个观察无效；
4. 多个普通细节共同产生的效果，优先保存为“效果链”而不是拆成零碎技巧；
5. 只有长期可调用、证据充分、边界清楚的知识进入 BKP；
6. 单书最高默认仍是 `Work-specific Pattern`，不升级为普遍写作定律。
