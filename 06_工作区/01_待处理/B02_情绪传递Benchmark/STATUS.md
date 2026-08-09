# B02 情绪传递 Benchmark Status

- 状态：`B02_G_ROUND2A_REVEALED_ANALYSIS_READY`
- 更新时间：2026-08-10
- 当前阶段：B02-G Round 2A mapping 已正式揭盲。**作者盲评已封存；Controller 独立评审已完成；外部 AI 独立评审已完成；现在允许进行 condition 级结果分析。** 12 个正式 run 仍保持冻结，不得修改或重跑。
- 封存 SHA256：`0f604478484b86d511246086311ff24a41533e6a375c2f1e62da2e3a149018c0`
- Round1 evidence is exploratory; not production-ready and not sufficient for KB/Skill promotion.
- 方法学限制（v0.2 记录）：作者评审存在 Controller 先行意见暴露（组3 不作为独立投票）；三任务匿名映射完全相同（A=G2/B=G1/C=D0）——Round2A 已通过 balanced permutation 与作者先评流程修正。

## 已完成

- [x] GitHub main 安全同步与本地状态核对
- [x] 三个上游冻结（Apodictic / creative-writing-skills / oh-story），记录 commit、LICENSE、restricted-source
- [x] `B02_上游冻结与适配事实表_v0.1.md` 已提交
- [x] B02 角色分轨：B02-G（生成）与 B02-R（诊断）分离，B02-G 先行
- [x] D0 / G1 / G2 三个 Runner 的最小机制注入首版冻结
- [x] 三个中性 base task（T1 爱情 / T2 权力 / T3 丧失）冻结
- [x] base prompt 机制泄露审计通过
- [x] 正式执行协议 v0.1 冻结
- [x] Controller 首轮复核：发现 Treatment 内容提示污染风险
- [x] G1/G2 注入去案例化修订
- [x] 重生成 6 个 Treatment runner 输入，D0 三个输入确认未改动
- [x] `runner_manifest.json` 更新注入字符/token 成本与逐条来源
- [x] `B02_G_Treatment内容提示污染审计_v0.1.md` 全部通过
- [x] Controller 最终复核通过
- [x] `06_工作区/01_待处理/B02_情绪传递Benchmark/00_控制/B02_G_Controller最终放行_v0.1.md`
- [x] B02-G 第一轮 9-run 正式执行完成（3 任务 × D0/G1/G2）
- [x] 确定性/格式检查完成（9/9 输出、无基础设施失败、无 retry、T1 无禁用情绪词、输入冻结未变）
- [x] Controller-only 匿名映射（D0/G1/G2 → 方案A/B/C）已生成
- [x] 作者匿名评审包已生成（3 组 × 方案A/B/C）
- [x] 作者盲评完成并在揭盲前封存（含 Controller 辅助判断 diagnostic-only 分轨记录）
- [x] 揭盲：三任务映射一致 A=G2 / B=G1 / C=D0；G1 在三个任务中均获得正向作者信号，但 Round1 作者评审存在 Controller 先行意见暴露，胜场统计不具严格独立性；全部输出不达生产级
- [x] 机制级结果分析完成（逐规则五类标记；成本为 Round1 observed execution cost，仅观察不归因）
- [x] 方法学修订版 v0.2 完成并入库（作者评审独立性下调、匿名映射重复限制、机制/成本因果表述降级、副作用降为假设）
- [x] STATUS 概念修正："情绪重量无专属物件承重" → "人物化具体性不足或情绪表达落入通用化表现"；明确物件不是 B02 要求
- [x] Round2A 单机制隔离实验设计冻结（M1 解释抑制 / M2 人物特异性反应）
- [x] 两个新异质任务冻结（T4 亲密关系·隐瞒与信任 / T5 身份与利益·合伙人信任危机）
- [x] 12-run 重复结构（2 tasks × 3 conditions × 2 repetitions）
- [x] Balanced permutation 匿名映射冻结（D0/M1/M2 在 A/B/C 位置均衡分布）
- [x] 评审隔离流程冻结（作者先评 → 封存 → Controller 后评）
- [x] 机制泄露与内容污染审计 v0.1 通过（6 类检查项）
- [x] Controller 复核要求 v0.1 修订完成（删除 T4 物件提示、固定 T4/T5 latent truth、删除 T5 成品台词）
- [x] 机制泄露与内容污染审计 v0.2 通过（8 类检查项全部通过）
- [x] Controller 最终放行 `B02_G_Round2A_Controller最终放行_v0.1.md` 已生成，状态转为 `B02_G_ROUND2A_READY_TO_RUN`（未运行）
- [x] 旧匿名 mapping 因 `PRE_RUN_MAPPING_EXPOSURE` 正式作废（发生在任何正式 output 生成之前；未查看任何正式结果；不涉及根据结果重新随机；不改变 D0/M1/M2、任务、重复次数或评审问题）
- [x] 新匿名 mapping 在正式 output 前独立生成并 Local Only 封存（`blind_map_presealed_r2a.json`，SHA256 见 `B02_G_Round2A_blind_map_seal_v0.1.md`），作者全部评审完成前不得公开
- [x] 12-run 正式执行完成（2 tasks × 3 conditions × 2 repetitions，全部成功，retry=0）
- [x] 确定性检查完成（纯机械：12/12 输出存在非空、exit=0、输入 hash 未变、mapping seal 未变、run order 未变）
- [x] 作者盲评包已生成（4 组 × 方案 A/B/C，Local Only，无泄露审计通过），空白评审模板 `author_blind_review_record_r2a.md` 已生成待作者填写
- [x] 作者 G1–G4 盲评已完成并封存（`author_blind_review_record_r2a_SEALED.md`，SHA256 `0f604478…`），`author_blind_review_seal_r2a.json` 已生成
- [x] Controller 独立评审已完成
- [x] 外部 AI 独立评审已完成
- [x] 正式揭盲完成（`B02_G_Round2A_正式揭盲_v0.1.md`），mapping SHA256 校验通过，状态转为 `B02_G_ROUND2A_REVEALED_ANALYSIS_READY`

## 揭盲后核心结论摘要（以 v0.2 为准）

- Round1 定位：exploratory mechanism evidence；非 KB READY、非 PRODUCTION READY、非 B02 COMPLETE。
- CONTINUE_VALIDATION（候选正向信号，非已证明机制）：具体细节/物件承重（G1-4/G2-4 同族）、解释抑制（G1-5/G2-7 同族，较强正向信号）、反通用动作模板（G2-6）、潜台词对话（G1-7）；均未完成单机制消融，因果归因未成立。
- MODIFY_AND_RETEST：对话循环（G1-2）、压力反应库与内心化（G2-1/G2-3）。
- SIDE_EFFECT_HYPOTHESIS（不建正式约束卡）：对话密度过高、情绪设计点/机关过密；不得据此推出“少写对话”等普遍规则。
- BASELINE_OVERLAP：G1-1、G1-6、G2-8。WEAK_OR_NO_SIGNAL：G1-3、G2-2、G2-5。
- Baseline 观察到的失败模式：结尾解释冲动、通用动作模板、人物化具体性不足或情绪表达落入通用化表现（观察差异，非已证明结论）。注意："专属物件"不是 B02 要求；物件只是人物化具体细节的一种可能实现；不使用物件本身不构成失败；后续不得把"物件承重"固化成写作规则。
- 成本：Round1 observed total tokens D0 24,283 / G1 88,255 / G2 35,682；每 cell 仅一次运行，差异是否稳定、是否由机制引起待后续重复验证。
- 生产可用性：本轮统一判定非 production ready；相对胜出仅为组内比较。

## 当前下一动作

现在允许进行 condition 级结果分析（作者票 / Controller 票 / 外部 AI 票的比较与汇总、condition 级成本比较、机制诊断）。

**12 个正式 run 仍保持冻结，不得修改或重跑。**

当前状态为 `B02_G_ROUND2A_REVEALED_ANALYSIS_READY`：mapping 已揭盲；三方评审均已完成；可以开始正式分析。

## 禁止

- 不设计 AI-write Candidate；
- 不启动 B02-R；
- 不新增候选；
- 不在看到结果后修改 Runner 并把补跑混入同一轮；
- 不以输出更长或 token 更多判优；
- 不修改已封存的作者评审记录；Controller 辅助判断不得合并入作者票；
- 不把首轮结果直接写入 `04_写作知识库` 或生产 Skill；
- 不因某 Runner 相对胜出而判定其整套规则有效或已达生产级；
- 不重跑 / 不补写 / 不修改任何已完成的正式 run（12 个 run 与冻结输入保持一致）；
- 作者盲评封存前：不揭盲、不阅读任何正式正文、不做 A/B/C 评价、不报告 condition→A/B/C、不提供可通过统计特征推断身份的信息；
- 作者盲评封存后、Controller 独立判断完成前：不读取作者封存记录内容、不揭盲；Controller 独立判断期间不得参考作者答案；
- 揭盲后：不修改或重跑任何已完成的正式 run（12 个 run 保持冻结）；
- 不测试 M1+M2 组合；
- 不把"物件承重"写成必须规则；
- 不建立"少写对话"等正式规则；
- 不修改 B09 Local Only 产物；
- 不改动用户手动模型 / provider / reasoning / CLI 配置。
