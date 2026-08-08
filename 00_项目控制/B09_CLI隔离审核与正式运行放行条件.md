# B09 CLI 隔离审核与正式运行放行条件

> 日期：2026-08-09
> 结论：独立 OS 进程隔离探针通过，但在正式 12 组运行前还需完成一次最小运行时 preflight。目的不是继续折腾 Agent 基础设施，而是排除文件读取与全局 Skill 污染两个会直接破坏 Baseline 的因素。

## 1. 已通过

本地已验证：

- `codex exec` 可用；
- CLI 版本：`codex-cli 0.147.0-alpha.6.5`；
- 固定模型：`deepseek-v4-flash`；
- reasoning effort：`high`；
- `--ephemeral` 独立执行；
- Probe-X / Probe-Y 为不同 session，Y 无法复述 X；
- 正式 Round 01 可采用 12 个独立 OS 进程，不再依赖当前失效的 subagent 消息投递。

## 2. 为什么还不能直接使用 `-C runner-dir -s workspace-write`

`workspace-write` 的主要边界是“写入限制”，不是“只能读取 cwd”。因此把 Runner 的 cwd 指向一个最小目录，并不能单独证明 Runner 无法读取仓库中的 pilot、其他 Runner、旧分析或全局文件。

正式 Benchmark 应尽量把“输入隔离”做成数据流隔离，而不是只依赖提示自律。

## 3. 正式输入方式

每次 Runner 使用一个新的空临时目录，目录位于仓库之外，例如系统 TEMP 下随机 UUID 路径。

Runner 不接收 AI-write 仓库根路径，不接收原著路径，不接收 `_local_runs` 路径。

Controller 将以下内容拼成一个完整 stdin payload：

1. 当前 Runner 的方法提示；
2. 统一输出合同；
3. manifest 必要信息（作品匿名 ID、source SHA256、coverage、窗口范围，不必包含真实本地路径）；
4. OPENING 冻结窗口正文；
5. MIDDLE 冻结窗口正文；
6. 明确要求只依据 payload 分析，不调用文件系统补充材料。

优先使用 `codex exec` 从 stdin 接收整个任务。不要把 120k+ 字符作为 Windows 命令行参数。

## 4. 正式输出方式

Runner 不需要写项目文件。

优先：

- sandbox 使用 `read-only`；
- Runner 将完整结果输出到 stdout；
- 输出使用固定 envelope，例如 `===01_EVIDENCE_NOTES===` / `===02_INTERPRETATION===` / `===03_MECHANISM_CARDS===` / `===04_SELF_LIMITS===`；
- Controller 在进程退出后把 stdout 拆成四个 Markdown 文件并写回对应 Local Only 目录；
- Controller 再运行 deterministic checker。

如果当前 CLI 的 read-only 模式在 Windows 上无法稳定完成纯文本任务，必须先做一个小型写/读隔离 probe；只有证明没有扩大读取范围后，才可使用 `workspace-write` 回退。

## 5. 专用 Benchmark CODEX_HOME

正式运行优先使用一个专用本地 `CODEX_HOME`，不要直接复用日常 Codex 环境。

该 home 只保留让 `deepseek-v4-flash` 工作所必需的：

- provider/model 配置；
- API 认证；
- 必要 CLI 配置。

不得复制：

- 用户自定义 Skills；
- 插件目录；
- MCP 配置（除非 CLI 无法启动且能证明与模型调用必需）；
- 历史会话；
- 小说项目 Agent 指令；
- 任何旧 Benchmark 输出。

密钥不得写入 Git、日志或 prompt。若必须登录专用 home，使用本机现有安全凭证来源完成，stdout/stderr 必须避免打印密钥。

目的：保证 D0 真的是 Minimal Baseline，而不是“Minimal prompt + 用户全局写作 Skill”。

## 6. Preflight v2

正式 12 组前只做一个很小的测试：

1. 使用正式计划中的专用 CODEX_HOME；
2. 新建仓库外空临时 cwd；
3. `--ephemeral`；
4. `-m deepseek-v4-flash`；
5. reasoning effort=`high`；
6. 优先 `-s read-only`；
7. stdin 传入一个短任务；
8. 要求 stdout 按固定 envelope 返回两段文本；
9. 确认退出码 0、模型调用成功、无依赖仓库文件、无全局 Skill/插件注入证据。

Preflight v2 PASS 后无需再暂停，可直接进入正式 12 组。

## 7. 运行顺序随机化

由于 provider 不暴露精确模型快照，且 seed 不可固定，本轮避免固定使用 `D0 → A → B → C` 的时间顺序。

Controller 在任何正式 Runner 启动前生成并保存 12 组的随机执行顺序；生成后不得根据输出调整顺序。

记录：

- 随机顺序生成时间；
- 12 个 run id 的固定 permutation；
- 每个 run 的 started_at / finished_at；
- CLI 版本；
- model slug；
- reasoning effort。

如果本地模型目录能读取 `deepseek-v4-flash` 的结构化元数据，则在正式运行开始前与 12 组完成后各保存一次元数据哈希；若哈希变化，正式结果需标记 model-drift risk。

## 8. 单次运行结果的统计定位

本轮无法固定 seed，也没有精确服务端模型快照，因此每个方法只有一次正式生成时，结果只能作为 Round 01 的初筛证据，不能把小差距解释成稳定优势。

盲审后如果两个方案非常接近或 Judge 分歧明显，再针对争议样本做重复运行估计方差，不必现在把全部 12 组重复多次。

## 9. 认证副作用判断

当前 CLI 已切到 DeepSeek API key 登录。正式 Benchmark 期间不要再切回 ChatGPT 登录，以免中途改变运行环境。

插件目录 401 警告本身不影响文本模型调用，但正式运行仍应通过专用 Benchmark CODEX_HOME 避免把日常插件/Skill 环境带入实验。

桌面端 ChatGPT 会话与这次 CLI Benchmark 分开处理；Benchmark 完成后如有需要再恢复 CLI 的 ChatGPT 登录。

## 10. 放行标准

满足以下条件后，Controller 放行正式 12 组：

- 独立 OS 进程 probe：PASS；
- 专用最小 CODEX_HOME：PASS；
- 仓库外空 cwd：PASS；
- stdin payload：PASS；
- stdout envelope：PASS；
- read-only 优先运行：PASS，或有记录的安全回退；
- 12 组执行顺序已提前随机冻结；
- 同一 CLI / model slug / reasoning effort；
- pilot 与其他 Runner 不进入任何正式 Runner 上下文。

正式规模仍为 `3 作品 × 4 Runner = 12`，每个 Runner 一次同时处理同一作品的 OPENING + MIDDLE。
