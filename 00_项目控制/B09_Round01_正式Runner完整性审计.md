# B09 Round 01 正式 Runner 完整性审计

> 日期：2026-08-09
> 审计结论：**PASS — 允许进入匿名化与 Blind Judge 阶段**
> 边界：本审计只确认实验执行有效性，不评价 D0 / A / B / C 谁更好。

## 一、Controller 结论

根据本地执行 Agent 提交的正式 Round 01 完整性报告，正式 12 组 Runner 满足当前 B09 第一轮进入盲审的硬条件：

- Preflight v2 PASS；
- 使用专用最小 Benchmark `CODEX_HOME`，无用户 Skills / 插件 / MCP / 历史会话污染；
- 12/12 使用独立 OS 进程；
- 12/12 使用 `--ephemeral`；
- 12/12 使用仓库外临时 cwd；
- 12/12 使用 read-only sandbox；
- 12/12 通过 stdin 接收当前 Runner 的方法提示 + 同一作品 OPENING + MIDDLE 双窗口；
- 12/12 不读取 pilot、其他 Runner、Judge 或既有分析；
- 模型统一为 `deepseek-v4-flash`，reasoning effort 统一为 `high`；
- 12 组执行顺序在运行前随机冻结，未根据输出动态调整；
- 12/12 deterministic check PASS；
- 三个 source SHA256 运行前后均与 manifest 一致；
- Local Only / Git 边界保持安全。

因此状态允许推进到：

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`

## 二、正式运行规模确认

正式有效数据为：

`3 作品 × 4 Runner = 12 个独立运行`

每个 Runner 一次同时读取该作品：

- `OPENING`
- `MIDDLE`

并能够进行跨窗口判断：阶段漂移、反证/边界、仅单窗口成立、两窗口均支持等。

此前 24 组单窗口同会话结果仍只作为 pilot，不进入本轮排名、Judge 或人工赢家判断。

## 三、执行环境记录

- CLI：`codex-cli 0.147.0-alpha.6.5`
- 模型：`deepseek-v4-flash`
- Provider：DeepSeek
- Reasoning effort：`high`
- 精确服务端模型快照：`unavailable`
- temperature / seed / max_output：运行时未暴露则保持 `unavailable`
- 正式总 token（CLI 报告）：约 950,506
- 单组 token：约 46,897–118,175
- 单组输出字符：约 9,024–14,698

输出规模存在自然差异，但没有出现某一方法通过数量级更长输出获得明显格式优势。Token 成本差异必须作为后续“能力收益 / 成本”维度保留，不能只评质量不评代价。

## 四、随机执行顺序

正式顺序在运行前冻结为：

1. WN-A-D0
2. WN-A-B
3. WN-B-B
4. WN-B-C
5. WL-A-D0
6. WL-A-C
7. WN-A-C
8. WN-B-D0
9. WL-A-A
10. WL-A-B
11. WN-A-A
12. WN-B-A

此设计用于降低服务端模型状态随时间变化时，对固定总是先跑/后跑某一 Runner 的系统性偏差。

## 五、Retry 判定

`WN-B-C` 首次尝试发生 DeepSeek API 流式连接中断，5/5 网络重试后 process exit = 1，且没有形成可评审输出。

处理方式符合 Benchmark 有效性要求：

- 首次基础设施失败单独留档；
- 不把网络失败计为方法内容失败；
- 第二次使用全新独立进程；
- 输入、方法提示、模型条件保持一致；
- `retry_count=1` 明确记录；
- 最终 deterministic check PASS。

因此该组可以进入正式盲审，但 Judge 不应看到 retry 身份信息，以免形成先验偏见。

## 六、模型漂移风险的正确表述

运行前后专用 `CODEX_HOME/models.json` 哈希一致，说明：

- 本地模型目录/元数据在正式运行期间未发生可观察变化。

但它**不能严格证明** DeepSeek 服务端 `deepseek-v4-flash` slug 背后的实际权重或服务实现绝对没有热更新。

因此正式结论应写为：

- `observable_local_model_metadata_drift = false`
- `remote_snapshot_immutability = unverified`

本轮通过随机冻结执行顺序降低该不可见风险，不把它视为阻塞项。

## 七、窗口边界风险

固定窗口可能截断自然场景，例如 WL-A 某些事件跨 OPENING / MIDDLE 的字符边界。

这不是 Runner 错误，而是采样 Benchmark 的固有限制。Judge 需要：

- 不因缺失窗口外上下文惩罚 Runner；
- 只检查 Runner 是否诚实承认边界；
- 若某个 Claim 依赖明显被截断的场景，应降低该 Claim 的确定性，而不是自行补全原著。

## 八、允许进入盲审，但仍禁止的行为

现在允许：

1. 对 `round-01-formal` 执行匿名化；
2. 生成 `_blind/` 与 Controller-only mapping；
3. 启动两个独立 Judge；
4. 形成仍保持匿名的人工成对盲评包。

仍然禁止：

- Judge 读取 `run_metadata.json`、运行顺序、token、retry 信息；
- Judge 读取真实 Runner 名称；
- Judge 读取 pilot；
- Judge 读取另一个 Judge 的结果；
- Controller 在人工盲评前揭盲；
- 根据一个总分宣布“总冠军”；
- 将 12/12 structural PASS 误写成方法质量 PASS。

## 九、下一阶段的评价重点

Blind Judge 不需要再重复 deterministic checker 已经完成的格式检查。应重点评：

- Evidence 是否真的支持 Claim，而不仅仅“引用了一个 ID”；
- Fact 与 inference 是否在语义上真正分开；
- 是否存在看似有证据、实际因果跳跃；
- OPENING 的发现是否被 MIDDLE 验证、限定或反驳；
- Mechanism Card 是否真的能迁移，而不是剧情摘要换名；
- 是否解释读者体验的因果链；
- 是否主动处理反例和边界；
- 对网络小说与世界文学是否出现明显方法偏科；
- 是否有“写得专业但对原创没有帮助”的输出。

## 十、审计结论

正式 Runner 阶段通过实验完整性审计。

下一状态：

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`

下一步：匿名化 → 两个独立 Blind Judge → 形成匿名人工 pairwise packet → 人工完成少量高价值选择后才揭盲。
