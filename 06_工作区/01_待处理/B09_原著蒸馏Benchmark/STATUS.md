# B09 Benchmark Status

- 状态：`ROUND02A_V01_PILOT_COMPLETE_V02_RERUN_READY`
- 更新时间：2026-08-09
- 当前阶段：Round 01 已完成并形成揭盲能力图；Round 02A v0.1 的 8/8 独立运行已成功，但因基础任务泄露目标机制、且 A/B 映射在汇报中提前公开，只保留为工程 pilot。已完成 v0.2 修正协议，准备正式重跑原创迁移 Smoke Test。

## Round 01 已完成

- [x] 3 作品 × 2 冻结窗口
- [x] D0 / A / B / C 正式 12/12 独立 Runner
- [x] deterministic check 全 PASS
- [x] 双 Blind Judge + Evidence fidelity 核证
- [x] 人工评审、揭盲与来源贡献分析
- [x] `00_项目控制/B09_Round01_揭盲能力图结论.md`

Round 01 不选单一 Skill；结论按能力吸收、改造、合并。

## Round 02A v0.1 定位

v0.1 执行层面通过：

- 8/8 独立运行完成；
- exit 0，retry 0；
- 逐运行 token / 时长 / 输出字符已记录；
- 独立 OS 进程、专用 CODEX_HOME、read-only、`--ephemeral` 等隔离正常。

但不能作为能力增益正式证据，原因：

1. Control 基础题已经明显提示了各目标能力的关键操作；
2. 执行汇报提前公开了 A/B → Control/Treatment 映射，作者盲评失效。

详见：

`00_项目控制/B09_Round02A_v01偏差审计与重跑决定.md`

v0.1 Local Only 产物全部保留，只作为原创迁移工程 pilot，不据此淘汰或确认 K1–K4。

## Round 02A v0.2

正式修正协议：

`00_项目控制/B09_Round02A_原创迁移SmokeTest_v0.2.md`

仍测试四项 Round 01 核心候选：

1. 可计算风险系统；
2. 外部约束改变表达形式；
3. 主动诱发式信息获取 / 反应测试；
4. 可逆证据与竞争性解释。

规模仍为：

`4 个原创任务 × 2 版本 = 8 个独立运行`

### v0.2 的关键修正

- 基础题只描述作者目标、人物处境与必要事实，不提示解决方法；
- Treatment 才追加目标能力操作原则；
- A/B 映射在作者完成四组选择前只能存在于 Controller-only 文件；
- 执行完成汇报不得打印或暗示 A/B 对应关系；
- 作者只回答具体剧情方案：更愿意继续写、哪个更自然、最想保留哪个设计；
- 内部 Skill / 机制 / 来源贡献由 Controller 分析。

## 当前下一动作

本地 Agent 同步最新 `main` 后，严格执行：

`00_项目控制/B09_Round02A_原创迁移SmokeTest_v0.2.md`

完成 8 个独立运行并生成匿名展示包后暂停。

执行完成汇报只能包含：8/8 完整性、基础设施异常、成本统计、blind map 已生成但未公开、展示包已生成。

**禁止在作者完成四组选择前输出 A/B 映射。**

## 禁止

- 不把 Round 01 / Round 02A 候选直接写入 `04_写作知识库`；
- 不按外部 Skill 选总冠军；
- 不让作者学习术语后再评分；
- 不因 Treatment 更长而判定更好；
- 不根据 v0.1 结论判断 K1–K4 有效或无效；
- 不自行开始 Round 02B。
