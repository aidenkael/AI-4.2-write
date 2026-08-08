# B09 Round 01 Status

- 状态：`BLIND_JUDGING_COMPLETE_READY_FOR_HUMAN_PAIRWISE`
- 更新时间：2026-08-09
- 当前阶段：正式 12 个双窗口 Runner、匿名化、两个独立 Blind Judge 与人工盲评包均已完成。下一步只做少量人工成对盲评；人工完成前继续保持 blind map 封闭，不揭盲、不宣布方法赢家。

## 已完成

- [x] Benchmark 总设计
- [x] B09 第一轮执行协议
- [x] 3 样本 × 2 窗口冻结规则
- [x] D0 / A / B / C 四 Runner 协议
- [x] Evidence / Interpretation / Mechanism Card 统一合同
- [x] 样本 SHA256 / 章节边界冻结器
- [x] Runner 输出确定性检查器
- [x] Blind Judge 协议
- [x] Local Only / gitignore 保护
- [x] Phase 1–2：样本筛选与冻结
- [x] 单窗口 pilot 24 组完成并记录为无排名资格的工程 pilot
- [x] Pilot 偏差审计：单窗口粒度 + 同会话串扰风险
- [x] subagent 隔离失败后按协议停止
- [x] `codex exec` 独立 OS 进程隔离探针 PASS
- [x] CLI Preflight v2 PASS
- [x] 专用最小 Benchmark CODEX_HOME
- [x] 仓库外 cwd + `--ephemeral` + read-only
- [x] stdin 双窗口 payload + stdout envelope
- [x] 固定 `deepseek-v4-flash` + reasoning effort `high`
- [x] 正式运行前随机冻结 12 组执行顺序
- [x] 正式 12/12 双窗口独立 Runner 完成
- [x] 正式 12/12 deterministic check PASS
- [x] 三个 source SHA256 前后复验一致
- [x] 正式 Runner 完整性审计 PASS
- [x] Blind packet v2 附每个 sample 共用冻结 `_source/`
- [x] 两个独立 Blind Judge 完成 J01–J12 + S1/S2 + sample 排序 + 跨作品稳定性
- [x] Judge Evidence fidelity 回到冻结 `_source/` 核证
- [x] `human_pairwise_packet.md` 完成，共 6 组 pair
- [x] 匿名化脚本身份泄漏缺陷已修复：`check_report.json` 自动清理 Runner 身份与本地路径
- [x] 双 Judge 与人工盲评包审计完成：`00_项目控制/B09_Round01_双Judge与人工盲评包审计.md`

## 第一轮冻结样本

### WN-A：《庆余年》
- OPENING：span 1–6
- MIDDLE：span 373–378

### WN-B：《道诡异仙》
- OPENING：span 1–6
- MIDDLE：span 519–524

### WL-A：《一九八四》
- boundary mode：segment fallback
- OPENING：segment 1–6
- MIDDLE：segment 7–12

所有样本仍为 `coverage=sampled`，固定窗口不能外推成整书规律。

## 正式 Round 01 执行摘要

正式有效数据：

`3 作品 × 4 Runner = 12 个独立双窗口运行`

环境：

- `codex-cli 0.147.0-alpha.6.5`
- `deepseek-v4-flash`
- reasoning effort = `high`
- 独立 OS 进程
- `--ephemeral`
- 专用最小 CODEX_HOME
- 仓库外临时 cwd
- read-only sandbox
- stdin payload / stdout envelope

12/12 deterministic check PASS。

仅 WN-B-C 首次因 API 流式连接中断未形成输出；使用相同输入/提示和全新进程重试一次成功，作为基础设施 retry 留档，不计为方法失败。

## Blind Judge 摘要（仍匿名）

- Judge-1 / Judge-2 均完成 12 个匿名方案；
- S1 = 0；
- Judge-1：S2 24 条；
- Judge-2：S2 29 条；
- WN-A / WN-B 的整体匿名排序两 Judge 完全一致；
- WL-A 第二名、个别 Evidence fidelity 边界与压缩质量存在分歧；
- 两 Judge 均建议按能力维度选冠军，不设一个单一总冠军。

Judge-1 / Judge-2 使用同一 `deepseek-v4-flash`，属于独立上下文的重复评审而非异构模型评审；人工盲评承担最终异质纠偏。

## 匿名化工具修复

本轮执行时发现旧版匿名脚本复制的 `check_report.json` 中 `runner_dir` 可能泄露真实 Runner 路径。Controller 在 Judge 启动前已本地匿名化并复扫，未造成 Judge 身份泄漏。

GitHub 当前 `b09_anonymize.py` 已永久修复：复制 `check_report.json` 时自动清理 Runner 身份与本地路径字段。

## 当前下一动作：人工成对盲评

本地文件：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01-formal/human_pairwise_packet.md`

共 6 组 pair，每部作品 2 对。

人工只需要回答：

1. 哪个更能帮助原创设计？
2. 哪个更像漂亮空话？
3. 哪个机制最值得拿到新故事中测试？
4. 如果只能保留一个，保留哪个？

人工评审时仍不得：

- 打开 `_controller/blind_map.json`；
- 猜测或查询 D0/A/B/C 身份；
- 查看 run metadata / token / 方法说明；
- 因 Judge 排名直接照抄结论。

建议由本地 Agent 只展示 `human_pairwise_packet.md` 的匿名内容，记录用户选择和一句理由，不揭盲。

## 人工完成后的下一状态

`HUMAN_PAIRWISE_COMPLETE_READY_FOR_UNBLINDING`

届时才允许：

1. 固化人工盲评结果；
2. 打开 blind map；
3. 揭盲 D0/A/B/C；
4. 汇总 Judge + 人工结果；
5. 选各能力维度冠军，不选单一总冠军；
6. 判断哪些上游能力直接借鉴、二次改造、仅 Benchmark 或淘汰；
7. 设计第二轮跨题材迁移 A/B 测试。

只有迁移测试仍成立的机制，才进入 `04_写作知识库` 候选。
