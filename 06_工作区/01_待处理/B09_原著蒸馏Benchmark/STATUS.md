# B09 Round 01 Status

- 状态：`ROUND01_UNBLINDED_CAPABILITY_MAP_READY`
- 更新时间：2026-08-09
- 当前阶段：正式 Runner、匿名化、双 Blind Judge、人工机制评审、揭盲与来源贡献分析均已完成。Round 01 不选单一 Skill 冠军，已形成按能力吸收、改造、合并的来源贡献图；下一步是 Round 02 跨题材迁移验证设计。

## 已完成

- [x] 3 作品 × 2 冻结窗口
- [x] D0 / A / B / C 四 Runner 协议
- [x] 正式 12/12 双窗口独立 Runner 完成，deterministic check 全 PASS
- [x] CLI Preflight v2、专用最小 CODEX_HOME、独立 OS 进程、read-only、`--ephemeral`
- [x] 三个 source SHA256 前后复验一致
- [x] 正式 Runner 完整性审计
- [x] Blind packet v2 + 冻结 `_source/`
- [x] Judge-1 / Judge-2 独立盲审完成
- [x] Evidence fidelity 回到冻结原文核证
- [x] 匿名化脚本身份泄漏缺陷修复
- [x] 人工评审范式由“强制二选一”修正为“能力发现、去重、改造、组合”
- [x] P1–P6 机制层评审完成并保存 `human_mechanism_review.md`（Local Only）
- [x] 项目权威 README 已写入“工作台建设原则”
- [x] 人工机制评审完成审计
- [x] 首次打开 blind map 并完成 D0 / A / B / C 揭盲映射
- [x] 完成 Judge + Human Review + Evidence fidelity + 成本的来源贡献分析（Local Only）
- [x] Round 01 揭盲能力图结论：`00_项目控制/B09_Round01_揭盲能力图结论.md`

## 揭盲映射

| Sample | D0 Baseline | A oh-story adapted | B ani-book evidence-first | C AI-write Candidate |
| --- | --- | --- | --- | --- |
| WL-A《一九八四》 | R-KT7U | R-3ZT8 | R-5D26 | R-3GQW |
| WN-A《庆余年》 | R-FPX2 | R-GAWD | R-8YFS | R-GSK2 |
| WN-B《道诡异仙》 | R-ANL8 | R-L443 | R-VN9C | R-4YW3 |

## Round 01 当前核心能力候选

优先进入 Round 02：

1. 可计算风险系统；
2. 外部约束改变表达形式；
3. 主动诱发式信息获取 / 反应测试；
4. 可逆证据与竞争性解释（必须阶段性结算）。

这些仍只是迁移测试候选，尚未进入正式 `04_写作知识库`。

## 方法贡献摘要

- **D0 Baseline**：证明高价值发现不完全来自 Skill；必须长期保留最小基线以测量真实 Skill 增益。
- **A / oh-story adapted**：网文追读、信息控制、钩子与反转强；需控制冗余和模板化。
- **B / ani-book evidence-first**：fact / inference / hypothesis、confidence、counter-evidence 等证据纪律价值突出；需加强定位自动校验。
- **C / AI-write Candidate**：Reader-causality、反证与迁移测试命题稳定；需压缩长输出和成对回声。

不整体采用任何一个外部 Skill；按能力吸收并统一到 AI-write 自己的工作流。

## 人工评审证据边界

- P1、P2、P4、P5、P6：有用户正式判断。
- P3：无用户正式作答，仅有 Assistant 参考判断。
- P3 不得计作用户偏好；若它对后续关键结论有决定性影响，再补人工判断。
- 早期强制二选一答案仅为历史观察，不作为淘汰依据。

## 成本记录边界

揭盲汇报中的“单次运行 token 明细未留档”与正式 Runner 完成阶段曾报告的逐组 token / `run_metadata.json` 记录存在冲突。

本地复核前，不断言逐运行 token 已丢失。Round 02 必须把逐运行 token、时长、输出字符作为强制可复核字段。

## Round 01 禁止外推

- 不按胜场数选一个 Skill；
- 不因为某 Runner 总体领先就整套采用；
- 不把 GitHub 项目的原文、模板或受许可证约束实现直接拼入 AI-write；
- 不把 Round 01 机制直接写入正式知识库；
- 不把 sampled 窗口结论外推为整本作品规律。

## 当前下一动作：Round 02 设计

Round 02 的目标是测试：

> 这些从原著中蒸馏出的机制，离开原作和原题材后，能否仍然帮助作者完成原创设计、诊断与修订？

优先从 4 个核心候选中选择少量、互相区分度高的原创任务进行跨题材迁移 A/B 测试。

只有迁移后仍成立的能力，才进入 `04_写作知识库` 与正式 Skill 设计候选。
