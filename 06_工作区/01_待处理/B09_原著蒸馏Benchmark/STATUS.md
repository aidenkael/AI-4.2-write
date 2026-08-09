# B09 Benchmark Status

- 状态：`ROUND02A_DESIGN_READY_FOR_LOCAL_EXECUTION`
- 更新时间：2026-08-09
- 当前阶段：Round 01 已完成并形成揭盲能力图；Round 02A 已改为作者可理解的原创迁移 Smoke Test，不再要求作者直接评内部术语。

## Round 01 已完成

- [x] 3 作品 × 2 冻结窗口
- [x] D0 / A / B / C 正式 12/12 独立 Runner
- [x] deterministic check 全 PASS
- [x] 双 Blind Judge + Evidence fidelity 核证
- [x] 人工评审、揭盲与来源贡献分析
- [x] `00_项目控制/B09_Round01_揭盲能力图结论.md`

Round 01 不选单一 Skill；结论按能力吸收、改造、合并。

## Round 02A 设计

执行协议：

`00_项目控制/B09_Round02A_原创迁移SmokeTest_v0.1.md`

目标：测试 Round 01 核心能力离开原著后，是否真的改善原创小说设计。

优先测试：

1. 可计算风险系统；
2. 外部约束改变表达形式；
3. 主动诱发式信息获取 / 反应测试；
4. 可逆证据与竞争性解释。

## Round 02A 规模

`4 个全新原创任务 × 2 版本 = 8 个独立运行`

每个任务：

- Control：普通强基线；
- Treatment：同一模型、同一任务、同一输出合同，只增加对应能力的操作原则。

先沿用 `deepseek-v4-flash + reasoning high`，避免同时改变模型和方法。

执行顺序预先随机冻结；每次独立进程；强制记录 tokens / 时长 / 输出字符 / retry。

## 作者参与方式

作者不看 K1–K4、Control / Treatment、GitHub Skill 来源或内部评分。

作者只看 4 组匿名的具体原创剧情方案，判断：

- 哪份更愿意继续写；
- 哪份更自然、更不像 AI 套路；
- 哪个具体设计值得保留。

内部方法与 Skill 适用范围由 Controller 分析。

## 当前下一动作

本地 Agent 同步最新 `main` 后，严格按：

`00_项目控制/B09_Round02A_原创迁移SmokeTest_v0.1.md`

执行 Round 02A 的 8 个独立生成。

完成后先暂停，不做作者选择、不自行宣布能力有效、不进入 Round 02B。

向 Controller 汇报：8/8 完整性、随机顺序、逐运行成本、匿名映射是否安全，以及 4 组匿名方案的简要可展示包。

## 禁止

- 不把 Round 01 / Round 02A 候选直接写入 `04_写作知识库`；
- 不按外部 Skill 选总冠军；
- 不让作者学习术语后再评分；
- 不因 Treatment 更长而判定更好；
- 不自行开始 Round 02B。
