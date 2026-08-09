# B02 情绪传递 Benchmark Status

- 状态：`B02_G_READY_TO_RUN`
- 更新时间：2026-08-09
- 当前阶段：上游冻结、候选分轨、base task、正式协议与 Runner 输入均已完成；Treatment 内容提示污染已完成去案例化修订并通过审计；Controller 最终复核通过，**正式放行 B02-G 第一轮 9-run**。当前尚未运行正式生成。

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
- [x] `00_项目控制/B02_G_Controller最终放行_v0.1.md`

## 当前下一动作

正式执行 B02-G 第一轮：

1. 运行前一次性随机冻结 9 个 run id 的 `run_order.json`（Local Only）；
2. 按 `B02_G正式执行协议_v0.1.md` 执行 `3 任务 × 3 Runner = 9` 个独立运行；
3. 每运行记录 token、耗时、字符数、exit code、retry_count；
4. 允许的基础设施 retry 最多一次；若仍失败，停止并报告 Controller；
5. 全部完成后做确定性/格式检查；
6. 再生成每个任务 D0/G1/G2 → A/B/C 的 Controller-only 匿名映射与作者评审包；
7. 作者评审完成前不得揭盲。

## 禁止

- 不设计 AI-write Candidate；
- 不启动 B02-R；
- 不新增候选；
- 不在看到结果后修改 Runner 并把补跑混入同一轮；
- 不以输出更长或 token 更多判优；
- 不把首轮结果直接写入 `04_写作知识库` 或生产 Skill；
- 不修改 B09 Local Only 产物。
