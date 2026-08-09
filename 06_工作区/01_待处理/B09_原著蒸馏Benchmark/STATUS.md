# B09 Benchmark Status

- 状态：`ROUND02A_V02_AUTHOR_REVIEW_COMPLETE_READY_FOR_UNBLINDING`
- 更新时间：2026-08-09
- 当前阶段：Round 01 已完成；Round 02A v0.1 保留为工程 pilot；Round 02A v0.2 已完成 8/8 独立运行与 4/4 作者匿名方案评审。作者选择已固定，现允许首次打开 v0.2 blind map，并由 Controller 做能力增益与工作台适用位置分析。

## Round 01 已完成

- [x] 3 作品 × 2 冻结窗口
- [x] D0 / A / B / C 正式 12/12 独立 Runner
- [x] deterministic check 全 PASS
- [x] 双 Blind Judge + Evidence fidelity 核证
- [x] 人工评审、揭盲与来源贡献分析
- [x] `00_项目控制/B09_Round01_揭盲能力图结论.md`

Round 01 不选单一 Skill；结论按能力吸收、改造、合并。

## Round 02A v0.1

v0.1 的 8/8 运行仅作为工程 pilot：执行链通过，但基础题泄露目标方法且 A/B 映射提前公开，因此不作为能力增益证据。

详见：

`00_项目控制/B09_Round02A_v01偏差审计与重跑决定.md`

## Round 02A v0.2 已完成

正式协议：

`00_项目控制/B09_Round02A_原创迁移SmokeTest_v0.2.md`

测试四项候选能力：

1. 可计算风险系统；
2. 外部约束改变表达形式；
3. 主动诱发式信息获取 / 反应测试；
4. 可逆证据与竞争性解释。

已完成：

- [x] 4 个原创任务 × Control/Treatment = 8 个独立运行；
- [x] 8/8 exit 0、retry 0；
- [x] 独立 OS 进程、专用最小 CODEX_HOME、read-only、`--ephemeral`；
- [x] 逐运行 token / 时长 / 输出字符记录；
- [x] v0.1 输出与映射未进入 v0.2 Runner；
- [x] v0.2 A/B 映射在作者评审完成前保持封闭；
- [x] 4/4 作者匿名评审完成，回答已固定保存 Local Only。

## 作者评审原则

作者只判断具体原创剧情方案，不负责 Skill、机制术语、证据纪律或许可证判断。

本轮作者反馈关注：

- 哪份更愿意继续写；
- 哪份更自然、更像真实作者设计；
- 哪个具体设计最值得保留；
- 同时允许指出“设计过密”“AI 炫技”“流程说明书化”等副作用。

## 当前下一动作：揭盲与 Controller 分析

现在允许首次打开：

`_local_runs/round-02a-v02/_controller/blind_map.json`

揭盲后先做事实整理，不由 Agent 直接决定最终吸收方案。必须汇总：

1. T1–T4 每组 A/B → Control/Treatment 映射；
2. 作者已固定的 4 组选择与具体保留点；
3. Treatment 是否被作者偏好、偏好来自什么具体设计；
4. Control 是否已经自然具备同类能力；
5. Treatment 是否产生设计过密、模板化、流程说明书化等副作用；
6. 成本差异仅作独立参考，不以更长或更多 token 判优。

随后由 Controller 判断每项能力进入：

- `继续验证`；
- `专项能力`；
- `改造后再测`；
- `暂缓`。

并进一步确定它在 AI-write 工作台中应当作为：生成指导、诊断检查、修订建议、规划辅助或其他位置。

## 禁止

- 不把 Round 02A 结果直接写入 `04_写作知识库`；
- 不按外部 Skill 选总冠军；
- 不让 Agent 以 A/B 胜负直接替代 Controller 的适用性分析；
- 不自行开始 Round 02B；
- 不因 Treatment 更长、token 更多而判定更好。
