# B09 Round 01 Status

- 状态：`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`
- 更新时间：2026-08-09
- 当前阶段：正式 Round 01 的 12 个双窗口 Runner 已通过实验完整性审计，允许进入匿名化与 Blind Judge；尚未匿名化、未 Judge、未揭盲、未比较赢家。

## 已完成

- [x] Benchmark 总设计
- [x] B09 第一轮执行协议
- [x] 3 样本 × 2 窗口冻结规则
- [x] D0 / A / B / C 四 Runner 协议
- [x] Evidence / Interpretation / Mechanism Card 统一合同
- [x] 样本 SHA256 / 章节边界冻结器
- [x] Runner 输出确定性检查器
- [x] 匿名化工具
- [x] Blind Judge 协议
- [x] 本地 manifest / run 目录加入 `.gitignore`
- [x] Phase 1：筛选并检查本地来源
- [x] Phase 2：冻结 WN-A / WN-B / WL-A
- [x] Controller sanity check
- [x] `06_工作区/SourcePrepare/` 加入 `.gitignore`
- [x] Pilot：3 作品 × 2 单窗口 × 4 Runner = 24 组完成
- [x] Pilot：24/24 deterministic structural check PASS
- [x] Pilot 偏差审计：单窗口粒度 + 同会话串扰风险
- [x] 正式重跑决定记录
- [x] subagent 隔离探针失败并按协议停止
- [x] `codex exec` 独立 OS 进程隔离探针 PASS
- [x] CLI Preflight v2 PASS
- [x] 专用最小 Benchmark CODEX_HOME
- [x] 仓库外空 cwd + `--ephemeral` + read-only sandbox
- [x] stdin 双窗口 payload + stdout envelope
- [x] 固定 `deepseek-v4-flash` + reasoning effort `high`
- [x] 正式运行前随机冻结 12 组执行顺序
- [x] 正式 12/12 双窗口独立 Runner 完成
- [x] 正式 12/12 deterministic check PASS
- [x] 三个 source SHA256 运行前后复验一致
- [x] 正式 Runner 实验完整性审计 PASS

## 第一轮冻结样本

### WN-A：《庆余年》
- 边界模式：chapter
- 探测章节：750
- OPENING：span 1–6
- MIDDLE：span 373–378

### WN-B：《道诡异仙》
- 边界模式：chapter
- 探测章节：1042
- OPENING：span 1–6
- MIDDLE：span 519–524

### WL-A：《一九八四》
- 边界模式：segment fallback
- 可用 segment：19
- OPENING：segment 1–6
- MIDDLE：segment 7–12
- 固定窗口存在自然场景截断风险；Judge 只能根据窗口内证据判断，不能自行补全窗口外正文。

## Pilot 定位

现有 24 组单窗口同会话结果仍只作为工程 pilot：

- 验证样本、冻结器、合同、checker；
- 不进入 Blind Judge；
- 不用于方法排名；
- 不用于最终 Skill 采用决策。

## 正式 Round 01 执行摘要

正式有效数据：

`3 作品 × 4 Runner = 12 个独立运行`

每个 Runner 一次同时处理该作品：

- OPENING
- MIDDLE

环境：

- `codex-cli 0.147.0-alpha.6.5`
- `deepseek-v4-flash`
- reasoning effort = `high`
- 独立 OS 进程
- `--ephemeral`
- 专用最小 CODEX_HOME
- 仓库外临时 cwd
- read-only sandbox
- stdin payload
- stdout envelope

12/12 deterministic check PASS。

仅 `WN-B-C` 首次因 DeepSeek API 流式连接中断未形成输出；基础设施失败已单独留档，随后使用相同输入/提示、全新独立进程重试一次并 PASS，`retry_count=1`。

正式 Runner 完整性审计：

`00_项目控制/B09_Round01_正式Runner完整性审计.md`

## 残余风险

1. `models.json` 运行前后哈希一致只证明本地模型元数据未发生可观察变化，不能严格证明 DeepSeek 服务端同一模型 slug 的底层快照绝对不变；正式运行已通过预先随机顺序降低系统性偏差。
2. 固定窗口可能截断自然场景；该问题属于 sampled Benchmark 的边界条件，Judge 应检查 Runner 是否诚实处理不确定性，而不是补充窗口外信息。
3. Token / 输出成本存在方法差异，后续需要作为“能力收益 / 成本”单独比较，不能只比较文字质量。

## 当前下一动作：匿名化与 Blind Judge

允许对：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01-formal/`

执行正式匿名化。

随后启动两个彼此独立的 Judge，只允许读取：

- `05_Skills与自动化/B09_原著蒸馏Benchmark/JUDGE.md`
- 正式 `_blind/` 匿名包

Judge 不得读取：

- `run_metadata.json`
- token / 执行顺序 / retry 信息
- pilot 输出
- Runner Pack 身份说明
- blind map
- 另一个 Judge 的结果

Judge 完成后形成仍匿名的 `human_pairwise_packet.md`，人工只做少量高价值成对选择。

人工完成前：

- 不揭盲；
- 不宣布总冠军；
- 不决定正式采用哪个 Skill。

## 下一状态

匿名化 + 两个 Blind Judge + 人工盲评包完成后：

`BLIND_JUDGING_COMPLETE_READY_FOR_HUMAN_PAIRWISE`
