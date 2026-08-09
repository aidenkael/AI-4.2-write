# B02 情绪传递 Benchmark Status

- 状态：`B02_G_NEEDS_RUNNER_DECONTAMINATION`
- 更新时间：2026-08-09
- 当前阶段：上游冻结、候选分轨、base task、正式协议与 Runner 输入均已完成；Controller 已完成首轮复核。总体协议与 base task 通过，但 G1/G2 注入中存在与 T3 高度贴近的具体示例/结尾脚手架，需先做去案例化修订。**尚未运行任何正式生成。**

## 已完成

- [x] GitHub main 安全同步与本地状态核对
- [x] 三个上游冻结（Apodictic / creative-writing-skills / oh-story），记录 commit、LICENSE、restricted-source
- [x] `B02_上游冻结与适配事实表_v0.1.md` 已提交
- [x] B02 角色分轨：B02-G（生成）与 B02-R（诊断）分离，B02-G 先行
- [x] D0 / G1 / G2 三个 Runner 的最小机制注入首版冻结
- [x] 三个中性 base task（T1 爱情 / T2 权力 / T3 丧失）冻结
- [x] base prompt 机制泄露审计通过
- [x] 正式执行协议 v0.1 冻结
- [x] Controller 复核完成：base task 与总体协议通过
- [x] 发现 Treatment 内容提示污染风险并记录于 `00_项目控制/B02_G_Controller审查与修订要求_v0.1.md`

## 当前下一动作

只修订 G1/G2 注入：

1. 删除与 T1/T2/T3 可直接对应的具体剧情示例、动作清单和固定结尾处方；
2. 只保留抽象机制，不新增 AI-write 自创技巧；
3. 重生成 6 个 Treatment runner 输入，D0 不变；
4. 更新 runner_manifest 的注入字符/token 成本与来源；
5. 做 `Treatment 内容提示污染审计`；
6. 提交后暂停，等待 Controller 最终放行。

T1/T2/T3 base task 当前不改。

## 禁止

- Controller 再次放行前不运行 T1/T2/T3、不调用正式模型生成小说；
- 不生成匿名作者评审包；
- 不设计 AI-write Candidate；
- 不启动 B02-R；
- 不新增候选；
- 不写入 `04_写作知识库`；
- 不创建生产 Skill；
- 不修改 B09 Local Only 产物。
