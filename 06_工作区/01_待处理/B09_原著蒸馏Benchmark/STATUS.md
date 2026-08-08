# B09 Round 01 Status

- 状态：`HUMAN_MECHANISM_REVIEW_COMPLETE_READY_FOR_UNBLINDING`
- 更新时间：2026-08-09
- 当前阶段：正式 Runner、匿名化、双 Blind Judge 与人工机制评审均已完成；blind map 仍未打开。下一步允许揭盲，并按能力维度分析 D0 / A / B / C 的真实贡献，不评单一总冠军。

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
- [x] 人工机制评审完成审计：`00_项目控制/B09_Round01_人工机制评审完成审计.md`

## 人工评审证据边界

- P1、P2、P4、P5、P6：有用户正式判断。
- P3：无用户正式作答，仅有 Assistant 参考判断。
- P3 不得计作用户偏好；若它对后续关键结论有决定性影响，再补人工判断。
- 早期“如果只能留一个”的二选一答案仅保留为历史观察，不作为淘汰依据。

## 当前优先追踪的能力候选

- 可计算风险系统；
- 外部约束改变表达形式；
- 主动诱发式信息获取 / 反应测试；
- 可逆证据与竞争性解释；
- 能力—成本—后果系统（力量代价记账作为子机制）；
- 有动机的信息交付 / 戏剧化说明；
- 收益与历史债务绑定（需改造验证）。

重复或过窄机制优先合并、降级为子机制或舍弃，不按卡片数量扩张知识库。

## 当前下一动作：揭盲与来源贡献分析

现在允许 Controller 打开：

`_local_runs/round-01-formal/_controller/blind_map.json`

揭盲后必须建立“匿名 label → D0/A/B/C → 来源方法”的映射，并同时汇总：

1. 两个 Blind Judge 的维度判断；
2. 用户正式 Human Review（P3 单独标记无用户判断）；
3. Evidence fidelity 问题；
4. 机制新增价值 / 重复度；
5. 成本（token / 输出规模）仅作为独立维度，不以长文本自动判优。

## 揭盲后禁止的错误结论

- 不按胜场数选一个 Skill；
- 不因为某个 Runner 总体领先就整套采用；
- 不把 GitHub 项目的原文、模板或受许可证约束实现直接拼入 AI-write；
- 不把 Round 01 结果直接写入正式 `04_写作知识库`；
- 不把 sampled 窗口结论外推为整本作品规律。

## 下一状态

完成揭盲与来源贡献分析后：

`ROUND01_UNBLINDED_CAPABILITY_MAP_READY`

随后从高价值能力中选择少量候选进入 Round 02 跨题材迁移验证。只有迁移后仍成立的能力，才进入正式知识库 / Skill 设计候选。
