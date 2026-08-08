# B09 Round 01 Pilot 偏差与正式重跑决定

> 日期：2026-08-09
> 状态：Controller decision
> 目的：保留 Phase 3 pilot 的工程价值，同时阻止不满足实验有效性条件的数据进入正式盲审。

## 一、结论

本地已完成的 24 组输出（3 作品 × 2 单窗口 × 4 Runner）定义为：

`round-01-pilot-single-window`

这些输出：

- 保留；
- 不删除；
- 可用于检查输出合同、程序检查器、样本质量和方法提示的可执行性；
- **不得用于正式 Runner 排名、Blind Judge、人工赢家判断或上游采用决策。**

正式 B09 Round 01 必须重新运行：

`3 作品 × 4 Runner = 12 个独立运行`

每个运行一次同时接收该作品的 `OPENING + MIDDLE` 两个冻结窗口，并输出一套四文件合同。

---

## 二、为什么 24 组 pilot 不能直接进入盲审

### 偏差 A：运行粒度错误

B09 原始协议的分析单元是：

`一部作品 + 一个 Runner + OPENING/MIDDLE 两个窗口`

不是：

`一部作品 + 一个 Runner + 一个窗口`

A / B 方法都包含跨窗口检查：

- 检查 OPENING 规律在 MIDDLE 是否仍成立；
- 区分阶段性规律与较稳定规律；
- 检查节奏、人物、信息机制是否发生阶段漂移；
- 用第二窗口提供反证/边界。

把两个窗口拆开独立运行，会系统性削弱这些原本设计为跨窗口工作的能力，因此不能公平比较。

### 偏差 B：Runner 会话隔离不足

原协议要求四个 Runner 使用独立新会话；如果 subagent 不可用，应改用本地 Codex / Claude / 其他 Agent 的独立会话，而不是同一会话顺序生成。

本次 pilot 因 subagent 消息投递失败，改为同一会话顺序执行 24 组。虽然文件读取层面没有互读其他 Runner 输出，但同一模型会话可能保留前序方法提示、输出风格和推理轨迹，存在方法串扰风险。

因此：

- `other_runner_outputs_read=false` 只能证明文件层隔离；
- 不能证明会话级方法隔离；
- 本轮不满足正式方法比较的独立性条件。

---

## 三、Pilot 仍然证明了什么

本轮不是失败实验。它已经验证：

1. 三个 source manifest 可正常工作；
2. SHA256 前后核验有效；
3. 冻结窗口可稳定读取；
4. Evidence → Interpretation → Mechanism Card → Self Limits 合同可执行；
5. `b09_check_outputs.py` 可对 24 组输出完成结构检查；
6. 四种方法在统一输出预算下可以生成规模接近的结果；
7. `WL-A` 的 segment fallback 可运行；
8. 暴露了“单窗口执行”与“双窗口方法”的协议歧义；
9. 暴露了 subagent 不可用时不应降级为同会话执行这一有效性风险。

这些信息应作为 Benchmark 工程改进依据保留。

---

## 四、正式 Round 01 的唯一有效运行单元

一共 12 个运行：

```text
WN-A × D0  -> 同时读取 WN-A OPENING + MIDDLE
WN-A × A   -> 同时读取 WN-A OPENING + MIDDLE
WN-A × B   -> 同时读取 WN-A OPENING + MIDDLE
WN-A × C   -> 同时读取 WN-A OPENING + MIDDLE

WN-B × D0/A/B/C -> 同样规则
WL-A × D0/A/B/C -> 同样规则
```

每个运行只产生一套：

```text
01_evidence_notes.md
02_interpretation.md
03_mechanism_cards.md
04_self_limits.md
run_metadata.json
check_report.json
```

Evidence / Claim 必须明确标出 `OPENING`、`MIDDLE` 或 `两者`。

---

## 五、会话隔离是正式有效性硬门槛

正式 Round 01：

- 最优：12 个独立 Agent/subagent 会话；
- 可接受：顺序启动 12 个完全独立的新 Agent 会话/进程；
- 不接受：同一聊天/同一 Agent 会话通过“忘掉前面内容”顺序扮演四种方法；
- 不接受：Runner 能读取其他 Runner 的输出或 Judge 结果。

如果本地 Agent 无法自动创建真正独立会话/进程，**停止正式运行并汇报环境限制**，不得再次自动降级到同一会话。

独立运行可以由 Controller 负责准备输入文件、启动外部进程和收集输出；Runner 本身只获得：

- 当前 sample 的两个冻结窗口；
- 当前 Runner 方法提示；
- 统一输出合同；
- 必要 manifest 元数据。

---

## 六、目录规则

现有 24 组 pilot 不删除，建议保留原目录并在本地元数据中标记：

`validity = pilot_only_single_window_nonisolated`

正式结果写入新的目录，例如：

`_local_runs/round-01-formal/`

不要覆盖 pilot，以便未来审计实验偏差。

正式目录结构：

```text
round-01-formal/
├── WN-A/
│   ├── D0/
│   ├── A/
│   ├── B/
│   └── C/
├── WN-B/
└── WL-A/
```

不要再建立 `OPENING/`、`MIDDLE/` Runner 子目录；两个窗口属于同一次运行的共同输入。

---

## 七、正式运行完成门槛

进入匿名化前必须全部满足：

- 12/12 运行完成；
- 每个运行同时读取两个窗口；
- 12 个运行均为独立新会话/进程；
- source SHA256 与 manifest 一致；
- deterministic check 完成；
- 未读取其他 Runner 输出；
- 未读取 Judge；
- 无覆盖范围扩张；
- run metadata 明确记录隔离方式；
- pilot 输出未混入正式结果。

满足后状态才能推进到：

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`

否则不得运行 `b09_anonymize.py`。
