# B09 Round 01｜双 Judge 与人工盲评包审计

> 日期：2026-08-09
> 结论：匿名化、双 Judge、人工盲评包均完成，可进入人工成对盲评；揭盲前继续保持 Runner 身份隔离。

## 1. 审计结论

正式 Round 01 已完成：

- 3 个 sample 的匿名化；
- 每个 sample 4 个匿名 Runner；
- 每个 sample 共用冻结 `_source/OPENING.txt`、`MIDDLE.txt`、`manifest_info.json`；
- Judge-1 / Judge-2 两个独立 `codex exec` 进程；
- J01–J12 全维度评审；
- S1 / S2 findings；
- 每个 sample 的匿名排序；
- 跨作品稳定性判断；
- `human_pairwise_packet.md`。

当前没有需要重跑 Runner 或 Judge 的阻塞问题。

## 2. 匿名化泄漏修正

本轮发现旧版 `b09_anonymize.py` 会直接复制 `check_report.json`，其中 `runner_dir` 字段可能包含真实 Runner 路径。

本轮本地执行中，Controller 在 Judge 启动前已将盲包内 12 份 `check_report.json` 的身份路径改写为匿名标签路径，并复扫确认 Judge payload 未泄露 D0/A/B/C 身份。

该问题不影响本轮盲审有效性，但属于工具缺陷。

GitHub 后续已修复 `b09_anonymize.py`：复制 `check_report.json` 时自动清理 Runner 身份与本地路径字段，避免以后依赖人工修补。

## 3. 双 Judge 独立性

Judge-1 / Judge-2：

- 两个独立 OS 进程；
- `--ephemeral`；
- 专用最小 CODEX_HOME；
- 仓库外 cwd；
- read-only；
- 只读匿名包与冻结 `_source/`；
- 不读 `blind_map`；
- 不读 run metadata / token / retry / pilot / 其他 Judge 结果；
- 两个 Judge 独立随机 sample 与 label 呈现顺序。

两者都使用 `deepseek-v4-flash`。因此它们是独立上下文、独立执行的重复评审，但不是异构模型评审。二者高度一致说明同模型下评审稳定性较高，不能被解读为两个完全独立认知体系的交叉验证。

人工盲评承担最终异质纠偏，不因此追加第三个模型 Judge。

## 4. Judge 共识

### 高一致性

- WN-A 与 WN-B 的整体匿名排序，两 Judge 完全一致；
- S1 = 0；
- 两 Judge 都建议按能力维度选冠军，不设单一总冠军；
- 两 Judge 对一批高价值机制卡与可疑机制卡形成稳定共识。

### 共同认可的强机制卡

- 监视几何学（WL-A）
- 约束性对话（WL-A）
- 先让裁判承诺标准再出示证据（WN-A）
- 事件型雷达（WN-A）
- 伪造—自验闭环（WN-A）
- 力量—代价双轨支付（WN-B）
- 真假边界翻转引擎（WN-B）

### 共同认为可疑的机制卡

- 越界—恐惧—释放循环
- 温情插曲泄压阀
- 后台强者与动机不明者
- 跨界实物转移钩子

这些名称仍属于匿名评审阶段的分析标签，不代表已通过迁移测试或已进入知识库。

## 5. Judge 分歧

主要分歧集中在：

- WL-A 第二名的排序；
- 个别 Evidence fidelity 边界问题是否应判 PASS / WARN；
- J12 Compression quality 的 WARN 权重；
- “字段很整齐”究竟是可用结构还是模板化外观风险。

这些分歧适合进入人工盲评，而不适合继续增加同模型 Judge 数量。

## 6. Evidence fidelity 实际问题

Judge 对冻结原文核证后发现若干真实问题，主要类型：

- 章节定位错误；
- 时序颠倒；
- 将主角推断写成文本事实；
- 章末位置判断不准确；
- 名称归位错误；
- 时态偏差；
- 数量级描述放大；
- 转述被写成短证据；
- 行为强度被过度表述。

这证明 Judge v2 附带冻结 `_source/` 是必要设计。仅检查 Evidence ID 是否存在无法发现这些问题。

## 7. S1 / S2

- S1：0
- Judge-1：S2 24 条
- Judge-2：S2 29 条

当前没有任何匿名方案因系统性证据欺骗、严重范围外推或明显仿写风险而需要直接淘汰。

S2 主要集中在：

- Evidence 归位与定位；
- 时态 / 量词精度；
- 推断强度超过证据；
- 压缩与冗余。

## 8. 人工盲评包

`human_pairwise_packet.md` 已形成，共 6 组 pair：

- 每部作品 2 对；
- 包含领先且接近的 pair；
- 包含强方案与可疑方案的对照；
- 包含 Judge 分歧最大的候选；
- 附共识强卡、共识可疑卡和分歧焦点。

人工不需要阅读 12 份完整 Runner 输出。

## 9. 当前有效状态

`BLIND_JUDGING_COMPLETE_READY_FOR_HUMAN_PAIRWISE`

下一步只进行人工盲评。

人工完成前禁止：

- 打开 `blind_map.json`；
- 揭露 D0/A/B/C；
- 宣布某个 Skill 获胜；
- 根据 Judge 结果修改 Runner 输出；
- 将机制卡直接写入正式知识库。

人工盲评结束后，才进入揭盲、各维度冠军分析、上游能力采用判定与第二轮迁移测试设计。
