# B09 正式 Round 01 重跑任务

> 当前前置状态：独立 OS 进程 Probe 已通过；正式运行前必须完成 CLI Preflight v2。
> 目的：执行正式有效的 B09 Runner 数据；现有 24 组单窗口同会话结果只作为 pilot 保留。

## 0. 开始前

先同步 GitHub `main`，然后读取：

1. `00_项目控制/B09_Round01_Pilot偏差与正式重跑决定.md`
2. `00_项目控制/B09_CLI隔离审核与正式运行放行条件.md`
3. `00_项目控制/B09_原著蒸馏Benchmark_执行协议_v0.1.md`
4. `05_Skills与自动化/B09_原著蒸馏Benchmark/README.md`
5. `06_工作区/01_待处理/B09_原著蒸馏Benchmark/STATUS.md`
6. 三个 `_local_manifests/*.json`

现有 pilot 输出不得删除、覆盖或进入 Judge。

## 1. 已确认的正式执行引擎

本轮采用本地 `codex exec` 独立 OS 进程，不再尝试当前失效的 subagent 消息投递。

当前已验证条件：

- CLI：`codex-cli 0.147.0-alpha.6.5`
- 模型：`deepseek-v4-flash`
- reasoning effort：`high`
- 每次调用使用 `--ephemeral`
- Probe-X / Probe-Y 独立 session，隔离通过

12 个正式 Runner 必须继续保持同一 CLI、同一 model slug、同一 reasoning effort。

## 2. Preflight v2：正式 12 组前最后一道门槛

严格执行 `00_项目控制/B09_CLI隔离审核与正式运行放行条件.md`。

### 2.1 专用 Benchmark CODEX_HOME

优先创建本地专用、最小化 `CODEX_HOME`，只保留调用 `deepseek-v4-flash` 所需 provider/model/auth 配置。

不得加载用户日常：

- 自定义 Skills；
- 插件；
- MCP（除非能证明模型调用必需）；
- 历史会话；
- 小说项目 Agent 指令；
- 旧 Benchmark 输出。

密钥不得输出到日志、prompt 或 Git。

### 2.2 仓库外空 cwd

每个 Runner 使用系统 TEMP 下新的随机空目录作为 cwd，不把 AI-write 仓库作为 Runner 工作目录。

Runner 不接收仓库根路径、原著绝对路径、pilot 路径或其他 Runner 路径。

### 2.3 stdin 输入

Controller 根据 manifest 从本地只读源中提取两个冻结窗口，然后把下列内容拼成 stdin payload：

1. 当前 Runner 方法提示；
2. 统一输出合同；
3. manifest 必要元数据；
4. OPENING 正文；
5. MIDDLE 正文；
6. 只依据本 payload 分析、不得调用文件系统补充资料的约束。

不要把大文本放进 Windows 命令行参数。

### 2.4 stdout 输出

优先使用 `-s read-only`，Runner 不写项目文件，完整结果输出 stdout。

固定 envelope：

```text
===01_EVIDENCE_NOTES===
...
===02_INTERPRETATION===
...
===03_MECHANISM_CARDS===
...
===04_SELF_LIMITS===
...
```

Controller 在进程退出后拆分 stdout，写回 Local Only 正式 Runner 目录，再运行 checker。

### 2.5 Preflight v2 判定

用短任务验证：

- 专用 CODEX_HOME 可正常调用模型；
- 仓库外空 cwd；
- `--ephemeral`；
- `deepseek-v4-flash`；
- reasoning effort=`high`；
- `read-only`；
- stdin 成功；
- stdout envelope 成功；
- EXIT=0；
- 无必须依赖仓库文件或全局 Skill/插件的迹象。

若 PASS：无需再次向 Controller 暂停，可直接执行正式 12 组。

若 FAIL：立即停止并汇报，不自行扩大权限或回到共享会话。

## 3. 正式运行单元

正式 Round 01 一共 12 个独立运行：

- WN-A × D0/A/B/C
- WN-B × D0/A/B/C
- WL-A × D0/A/B/C

每个运行一次同时读取同一作品：

`OPENING + MIDDLE`

不要拆成单窗口 Runner。

每个运行必须做跨窗口判断：

- OPENING 机制在 MIDDLE 是否仍存在；
- 是否发生阶段漂移；
- MIDDLE 是否形成反证/边界；
- 哪些结论只适用于一个窗口；
- 哪些结论可谨慎标为“两窗口均支持”。

即使两窗口都支持，也不得外推成整书规律。

## 4. 正式运行顺序必须预先随机冻结

由于服务端不暴露精确模型快照、seed 不可固定，不允许固定按 `D0 → A → B → C` 的时间顺序执行。

正式 Runner 启动前一次性生成 12 个 run id 的随机 permutation，保存到 Local Only `run_order.json`；生成后不得根据输出修改。

记录：

- permutation；
- 生成时间；
- 每组 started_at / finished_at；
- CLI 版本；
- model slug；
- reasoning effort。

若可读取本地模型目录中的 `deepseek-v4-flash` 元数据，则在正式运行前后分别保存元数据哈希；若变化，标记 `model_drift_risk=true`。

## 5. 正式目录

正式结果仍保存在：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01-formal/`

建议：

```text
round-01-formal/
├── isolation_probe.json
├── preflight_v2.json
├── run_conditions.json
├── run_order.json
├── WN-A/
│   ├── D0/
│   ├── A/
│   ├── B/
│   └── C/
├── WN-B/
└── WL-A/
```

每个 Runner 最终目录：

```text
01_evidence_notes.md
02_interpretation.md
03_mechanism_cards.md
04_self_limits.md
run_metadata.json
check_report.json
```

## 6. 输入公平性

每个 sample 的四方法必须：

- 同一 CLI / 模型 / reasoning effort；
- 同一 source manifest；
- 完全相同 OPENING + MIDDLE 范围；
- 同一输出合同；
- 同一可获得参数；
- 不提供额外旧分析。

运行前重新核对 source SHA256。

模型精确快照、temperature、seed 等若不暴露，记录 `unavailable`，不得估造。

## 7. Runner 隔离

每个正式进程只收到：

1. 当前 sample 必要 manifest 元数据；
2. 当前 sample OPENING + MIDDLE；
3. 统一输出合同；
4. 当前 Runner 自己的方法提示。

不得收到：

- 其他 Runner 方法提示；
- 其他 Runner 输出；
- pilot 输出；
- Judge；
- blind map；
- 项目既有该书分析；
- 冻结窗口外正文。

Runner 不自行选择或扩展原著范围。

## 8. 输出与 deterministic check

Controller 拆分 stdout 后，对每组立即运行：

`05_Skills与自动化/scripts/b09_check_outputs.py`

结构失败允许修正：

- 格式；
- 缺字段；
- 错误 Evidence ID 引用。

但修复必须由一个新的独立进程完成，只提供原输入 + 当前失败输出 + deterministic error，不提供其他 Runner 信息。

不得因为检查失败：

- 改方法提示；
- 扩大原文范围；
- 读取其他 Runner；
- 查看 Judge；
- 修改评分标准。

保留首检报告与 retry count。

## 9. metadata 有效性字段

每组至少记录：

```json
{
  "formal_round": true,
  "input_windows": ["OPENING", "MIDDLE"],
  "independent_session": true,
  "isolation_method": "codex_exec_ephemeral_process",
  "stdin_payload": true,
  "repo_outside_cwd": true,
  "pilot_outputs_read": false,
  "other_runner_outputs_read": false,
  "judge_outputs_read": false,
  "model_snapshot": "unavailable_or_value",
  "model_drift_risk": false
}
```

无法诚实填写 `independent_session=true` 时，正式结果无效并停止。

## 10. 认证规则

正式 12 组期间保持当前 DeepSeek API key 运行方式，不再切换 CLI 认证模式。

优先在专用 Benchmark CODEX_HOME 中完成认证，避免日常插件/Skill 环境污染实验。

不要在 Benchmark 中恢复 ChatGPT CLI 登录；实验结束后再单独处理。

## 11. 正式 12 组完成后暂停

12/12 + deterministic check 完成后，不匿名化、不 Judge、不揭盲。

向 Controller 汇报：

- Preflight v2 PASS/FAIL；
- 专用 CODEX_HOME 是否成功；
- 12/12 是否独立进程；
- 12 组是否同时读取双窗口；
- 随机执行顺序；
- deterministic PASS/FAIL；
- 首次失败与 retry；
- source SHA256；
- CLI/model/参数；
- 输入/输出规模；
- tokens/耗时（可得多少报多少）；
- 模型元数据前后是否变化；
- 是否发生任何仓库/Local Only 风险；
- 双窗口方法协议是否仍有歧义。

不要报告哪个方法更好。

Controller 审计通过后才进入：

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`
