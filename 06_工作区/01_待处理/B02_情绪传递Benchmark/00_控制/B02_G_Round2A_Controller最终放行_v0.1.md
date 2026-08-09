# B02-G Round 2A｜Controller 最终放行 v0.1

> 日期：2026-08-10
> 结论：B02-G Round 2A 冻结输入通过全部最终一致性检查，**放行进入正式运行**。
> 前提：放行不等于已运行。12 个正式 run 尚未开始；正式运行后不得修改冻结输入并混入本轮。

## 一、最终复核项目

Controller 已复核以下冻结材料：

- `B02_G_Round2A_单机制隔离设计_v0.1.md`（含 balanced permutation 最终 mapping）
- `B02_G_Round2A_base_tasks_v0.1.md`（T4 / T5 两个中性 base task，含 latent truth）
- `M1_injection.txt` / `M2_injection.txt`（单机制注入）
- `T4_D0.txt` / `T4_M1.txt` / `T4_M2.txt` / `T5_D0.txt` / `T5_M1.txt` / `T5_M2.txt`（6 个 runner 输入）
- `runner_manifest_r2a.json`（运行清单）
- `B02_G_Round2A_机制泄露与内容污染审计_v0.2.md`（修订后重新审计）
- 当前 B02 STATUS

复核结果：**全部通过。**

## 二、最终 mapping（冻结，评审前不公开）

| 评审组 | 任务 | 重复 | A | B | C |
|---|---|---|---|---|---|
| G1 | T4 | R1 | D0 | M1 | M2 |
| G2 | T4 | R2 | M2 | D0 | M1 |
| G3 | T5 | R1 | M1 | M2 | D0 |
| G4 | T5 | R2 | M2 | D0 | M1 |

平衡验证（已通过）：

- D0：A:1 / B:2 / C:1 ✓
- M1：A:1 / B:1 / C:2 ✓
- M2：A:2 / B:1 / C:1 ✓
- 连续同字母检查：D0 A→B→C→B ✓；M1 B→C→A→C ✓；M2 C→A→B→A ✓

映射在正式运行前冻结；作者评审完成前不公开。实际 `blind_map.json` 在运行完成并确定性检查后由 Controller 生成并封存。

## 三、输入一致性结果

字节级核对结论：

1. D0 / M1 / M2 三个条件定义未变化（M1=解释抑制，M2=人物特异性反应，D0=无注入）；
2. M1 injection 未变化：`M1_injection.txt` 与 T4_M1 / T5_M1 末尾追加块逐字节一致；
3. M2 injection 未变化：`M2_injection.txt` 与 T4_M2 / T5_M2 末尾追加块逐字节一致；
4. T4 latent truth 在三个条件中完全一致（逐字节一致）；
5. T5 latent truth 在三个条件中完全一致（逐字节一致）；
6. 同一任务内 D0/M1/M2 除 injection 外完全一致（M1/M2 前缀 == D0 全文，仅末尾追加对应注入块）；
7. 两次 repetition 使用相同输入（每个 cell 单个输入文件复用两次，manifest `repetitions: 2`）；
8. 不存在 M1+M2 组合条件（runners 仅 T4_D0/T4_M1/T4_M2/T5_D0/T5_M1/T5_M2）；
9. 所有路径引用在目录迁移后均有效；
10. runner manifest 指向的新路径全部存在（base_tasks / design / injections / 6 个 runner 输入均确认存在）；
11. 目标仍为 `2 tasks × 3 conditions × 2 repetitions = 12 runs`（manifest `total_runs: 12`）；
12. 作者评审仍为 4 组三选一（G1–G4）；
13. 作者必须先完成全部 4 组评审并封存，Controller 在封存前不得阅读、分析或评价正文；
14. 成本仍只作为观察维度，不归因；
15. 不存在"使用物件""少写对话"等新增规则；
16. 不存在可直接复制的成品台词或情绪表现范例。

## 四、污染审计状态

`B02_G_Round2A_机制泄露与内容污染审计_v0.2.md`：**全部 8 类检查项通过**。

1. T4 具体物件/线索提示已彻底删除 ✓
2. Hidden truth 只固定故事事实，不含 M1/M2 写法指导 ✓
3. D0/M1/M2 获得完全相同的 hidden truth ✓
4. 不同 run 不再需要自行发明核心秘密 ✓
5. T5 成品台词已删除 ✓
6. Base task 无 M1/M2 机制泄露 ✓
7. M1/M2 injection 相互独立 ✓
8. 六个 runner 输入除 injection 外完全一致 ✓

## 五、评审隔离状态

严格执行 **作者先评 → 作者结果封存 → Controller 后评**：

1. 12 个 run 全部完成并确定性检查后，按 §二 mapping 生成 4 组匿名正文包；
2. 作者逐组评审（每组三篇），回答设计 §8 的 5 个问题；
3. 作者全部 4 组评审结果写入 `author_blind_review_record_r2a.md`（Local Only）并封存；
4. **作者封存之前，Controller 不得**给出任何 A/B/C 偏好、分析具体段落、提示哪一版"设计更聪明"、评价人物具体性、或阅读任何 run 的 output.md。

## 六、运行规模

`2 tasks × 3 conditions × 2 repetitions = 12 runs`

- 模型 `deepseek-v4-flash`；Reasoning `high`；Provider deepseek（responses API）；
- CLI `codex-cli 0.147.0-alpha.6.5`，`codex exec --ephemeral -s read-only`，stdin payload，仓库外随机临时 cwd；
- 每次独立进程与独立上下文；输出目标 900–1200 中文字；Timeout 900 秒；
- 运行顺序在正式运行前一次性随机冻结（`run_order.json`，Local Only）；
- **不得擅自修改用户手动模型 / provider / reasoning / CLI 配置。**

## 七、放行边界

本次只放行 B02-G Round 2A 的 12 个正式 run。

运行阶段只允许：

1. 执行 12 个冻结 runner；
2. 按协议处理最多一次基础设施 retry；
3. 记录 token / 耗时 / 字符数 / exit code；
4. 做确定性与格式检查；
5. 全部完成后生成匿名 A/B/C 映射与作者评审包。

正式作者评审前不得揭盲 D0/M1/M2。

**仍然禁止**：不设计 AI-write Candidate；不启动 B02-R；不新增候选；不在看到结果后修改冻结输入并把补跑混入本轮；不以 token 更多、输出更长判优；不把结果直接写入 `04_写作知识库` 或生产 Skill；不测试 M1+M2 组合；不把"物件承重"写成必须规则；不建立"少写对话"等正式规则。

若任一正式运行在允许的一次基础设施 retry 后仍失败，应停止并交回 Controller，不自行修改模型、权限、Prompt 或 Runner。
