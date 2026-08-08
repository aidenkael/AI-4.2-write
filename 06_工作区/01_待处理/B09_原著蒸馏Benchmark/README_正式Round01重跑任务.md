# B09 正式 Round 01 重跑任务

> 当前前置状态：`PILOT_COMPLETE_FORMAL_RERUN_REQUIRED`
> 目的：执行正式有效的 B09 Runner 数据；现有 24 组单窗口同会话结果只作为 pilot 保留。

## 0. 开始前

先同步 GitHub `main`，然后读取：

1. `00_项目控制/B09_Round01_Pilot偏差与正式重跑决定.md`
2. `00_项目控制/B09_原著蒸馏Benchmark_执行协议_v0.1.md`
3. `05_Skills与自动化/B09_原著蒸馏Benchmark/README.md`
4. `06_工作区/01_待处理/B09_原著蒸馏Benchmark/STATUS.md`
5. 三个 `_local_manifests/*.json`

现有 pilot 输出不得删除、覆盖或进入 Judge。

## 1. 先做隔离探针，不要直接跑 12 组

目标：证明本环境可以启动“真正独立的新 Agent 会话/进程”。

可接受方式：

- subagent，且能确认每个子代理只收到自己的任务；
- 本地 Codex/Claude/其他模型 CLI 的独立进程；
- 自动化启动的多个全新 session，每个 session 没有前序 Runner 对话上下文。

不可接受：

- 同一个聊天会话顺序扮演 D0/A/B/C；
- 仅靠提示“忘记之前内容”；
- 同一 Agent 上下文里隐藏前一结果但保留前一方法提示。

### 隔离探针

启动两个独立临时会话：Probe-X、Probe-Y。

只给：

- Probe-X：随机字符串 `B09-X-<随机8位>`，要求只输出收到的字符串；
- Probe-Y：另一个随机字符串 `B09-Y-<随机8位>`，要求只输出收到的字符串，并回答是否见过 X 的字符串。

判定：

- 两个会话各自只返回自己的字符串；
- Y 不知道 X；
- Controller 能证明它们不是同一个持续会话。

如果探针失败：

**立即停止。不要用同一会话回退，不要运行正式 12 组。汇报环境限制。**

如果探针通过，记录隔离方式到：

`_local_runs/round-01-formal/isolation_probe.json`

至少包含：方式、命令/会话类型（不含密钥）、时间、pass=true、备注。

## 2. 正式运行单元

正式 Round 01 一共只有 12 个运行：

- WN-A × D0/A/B/C
- WN-B × D0/A/B/C
- WL-A × D0/A/B/C

每个运行一次同时读取同一作品的两个冻结窗口：

`OPENING + MIDDLE`

不要把 OPENING 与 MIDDLE 拆成两个 Runner。

每个运行必须能执行跨窗口判断：

- OPENING 发现的机制在 MIDDLE 是否仍存在；
- 是否发生阶段漂移；
- MIDDLE 是否提供反证或边界；
- 哪些结论只能限定在某一窗口；
- 哪些结论可以谨慎标记为“两窗口均支持”。

即使两个窗口都支持，也不得外推成整书规律。

## 3. 正式目录

新建：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01-formal/`

结构：

```text
round-01-formal/
├── isolation_probe.json
├── run_conditions.json
├── WN-A/
│   ├── D0/
│   ├── A/
│   ├── B/
│   └── C/
├── WN-B/
└── WL-A/
```

每个 Runner 目录只有一套：

```text
01_evidence_notes.md
02_interpretation.md
03_mechanism_cards.md
04_self_limits.md
run_metadata.json
check_report.json
```

不要建立 `OPENING/`、`MIDDLE/` 子目录。

## 4. 输入公平性

每个 sample 的四种方法必须：

- 使用同一模型；
- 使用同一可获得的参数；
- 使用同一 source manifest；
- 同时读取完全相同的 OPENING + MIDDLE 字符范围；
- 使用同一最大输出预算；
- 除当前 Runner 方法提示外，不提供额外旧分析。

运行前重新核对 source SHA256。

如果模型名、temperature、seed、token usage 等运行时不暴露，记录 `unavailable`，不得估造。

## 5. Runner 隔离

12 个运行分别启动 12 个独立新会话/进程。

每个 Runner 只能收到：

1. 当前 sample 的 manifest 必要元数据；
2. 当前 sample 的 OPENING + MIDDLE 两个窗口；
3. 统一输出合同；
4. 当前 Runner 自己的方法提示。

不得收到：

- 其他 Runner 方法提示；
- 其他 Runner 输出；
- pilot 输出；
- Judge 协议结果；
- blind map；
- 项目中已有的该书分析。

Controller 可以准备输入和收集落盘；Runner 不自行挑选范围。

## 6. 输出与检查

每个 Runner 完成后立即运行：

`05_Skills与自动化/scripts/b09_check_outputs.py`

并保存 `check_report.json`。

结构失败允许只修：

- 格式；
- 缺字段；
- 错误 Evidence ID 引用。

不得因为检查失败：

- 改方法提示；
- 扩大原文范围；
- 读取其他 Runner；
- 查看 Judge；
- 重写评分标准。

保留首次失败记录与 retry count。

## 7. metadata 必须增加的有效性字段

每个 `run_metadata.json` 除原字段外增加：

```json
{
  "formal_round": true,
  "input_windows": ["OPENING", "MIDDLE"],
  "independent_session": true,
  "isolation_method": "<subagent/new_process/new_session>",
  "pilot_outputs_read": false,
  "other_runner_outputs_read": false,
  "judge_outputs_read": false
}
```

如果 `independent_session` 不能诚实写 `true`，该运行无效，停止正式 Round 01。

## 8. 完成后暂停

12/12 运行完成且 deterministic check 完成后，不匿名化、不 Judge、不揭盲。

先向 Controller 汇报：

- isolation probe 是否 PASS；
- 实际使用的隔离方式；
- 12/12 是否全部独立新会话；
- 每个运行是否同时读取 OPENING + MIDDLE；
- 12 组 deterministic check PASS/FAIL；
- 首次失败与 retry count；
- source SHA256 是否一致；
- 模型/参数可获得信息；
- 输入窗口字符数、输出字符数；
- Token/调用次数/耗时（运行时可得多少报多少）；
- 是否发现方法协议在双窗口条件下仍有歧义；
- Git/Local Only 是否安全。

不要报告哪个方法更好。

只有 Controller 审计通过，才允许进入：

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`
