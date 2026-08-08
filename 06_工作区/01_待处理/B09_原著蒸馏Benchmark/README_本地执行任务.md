# B09 第一轮｜本地 Agent 执行任务

> 任务状态：READY TO RUN
> 本文件只定义执行动作，不包含第三方原著正文。

## 任务目标

完成 B09 原著蒸馏 Benchmark 第一轮：

- 3 个本地样本；
- 4 个独立 Runner；
- 12 组标准化输出；
- 确定性程序检查；
- 匿名化；
- 2 个独立 Judge 盲审；
- 输出待人工盲评包。

在人工盲评完成之前，**不得揭盲，不得宣布哪个上游方案获胜。**

## 必读文件

开始前读取：

1. `00_项目控制/README_目录使用说明.md`
2. `00_项目控制/AI写作Skill_Benchmark设计_v0.1.md`
3. `00_项目控制/B09_原著蒸馏Benchmark_执行协议_v0.1.md`
4. `05_Skills与自动化/B09_原著蒸馏Benchmark/README.md`
5. `05_Skills与自动化/B09_原著蒸馏Benchmark/JUDGE.md`

## 硬性边界

- `01_原始素材` 全程只读；
- 不移动、覆盖、重命名、删除原始文件；
- 不把原著正文复制到 GitHub 跟踪目录；
- 不提交 `_local_manifests/`、`_local_runs/`；
- 不在日志里输出大段原著；
- 只保留支撑判断所需的短证据；
- Runner 不得扩展 manifest 冻结范围；
- Runner 之间不得互读输出；
- Judge 不得读取真实 Runner 映射。

## Phase 1｜选择 3 个样本

先只查看本地素材目录/已有索引/文件名和必要元数据，不做全书分析。

选择：

### WN-A

网络小说。优先选择能代表以下能力的作品：

- 持续阅读驱动力；
- 连载节奏；
- 期待—兑现；
- 爽点/悬念/信息释放；
- 长篇商业叙事。

### WN-B

网络小说。与 WN-A 尽量拉开方法差异，优先：

- 人物关系；
- 角色复杂性；
- 情绪推动；
- 潜台词；
- 群像或较复杂结构。

### WL-A

世界文学。优先选择：

- 人物心理；
- 内心与行为矛盾；
- POV/叙述距离；
- 情感或主题通过行动/意象表达。

不要因为某本书“更容易拆”就选它。三个样本的任务是制造方法差异压力。

为每个样本记录一句 `selection_reason`。

## Phase 2｜冻结样本

在仓库根运行：

```bash
python "05_Skills与自动化/scripts/b09_freeze_samples.py" \
  --source "<本地原著路径>" \
  --sample-id "WN-A" \
  --kind web_novel \
  --title "<作品名>" \
  --selection-reason "<一句话原因>"
```

WN-B 同上。

WL-A：

```bash
python "05_Skills与自动化/scripts/b09_freeze_samples.py" \
  --source "<本地原著路径>" \
  --sample-id "WL-A" \
  --kind world_literature \
  --title "<作品名>" \
  --selection-reason "<一句话原因>"
```

冻结完成后检查：

- 三个 manifest 均存在；
- SHA256 已生成；
- `raw_text_copied=false`；
- `coverage.mode=sampled`；
- OPENING/MIDDLE 均存在；
- 原始文件 mtime/size 未改变。

若章节探测错误，不要手工改原著。修正冻结器或另加“边界 override”方案后重新生成 manifest，并记录原因。

## Phase 3｜固定模型条件

在 `round-01/run_conditions.json` 记录：

```json
{
  "model": "<exact model>",
  "provider": "<provider>",
  "temperature": "<value or unavailable>",
  "seed": "<value or unavailable>",
  "max_output": "<value>",
  "runner_context_policy": "same frozen source windows only"
}
```

本轮不得在 A 用强模型、D0 用弱模型。

如果平台不支持固定 seed，接受随机波动，但必须如实记录；后续可用重复运行测方差。

## Phase 4｜运行 12 组 Runner

对每个 sample 分别运行：

- D0 Minimal Baseline；
- A oh-story Method Adaptation；
- B ani-book Evidence-first；
- C AI-write Candidate v0.1。

执行协议和精确方法说明全部来自：

`05_Skills与自动化/B09_原著蒸馏Benchmark/README.md`

### 隔离要求

最佳方式：四个独立 Agent / subagent 同时或分别执行。

如果没有 subagent：

- 每个 Runner 使用全新会话；
- 只给 source window + 对应 Runner 指令；
- 不把其他 Runner 文件放入上下文；
- Controller 负责文件落盘，不让 Runner 自己挑范围。

## Phase 5｜逐组程序检查

每个 Runner 完成后立即运行：

```bash
python "05_Skills与自动化/scripts/b09_check_outputs.py" \
  "06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01/WN-A/A" \
  --output "06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01/WN-A/A/check_report.json"
```

对 12 组全部执行。

### 处理规则

- 结构检查失败：允许 Runner 只修格式/缺失字段；
- 不允许 Runner 看 Judge 结果后改答案；
- 不允许为了通过检查新增原文范围；
- 修复后保留第一次失败报告，记录 `format_retry_count`。

## Phase 6｜匿名化

12 组均完成后：

```bash
python "05_Skills与自动化/scripts/b09_anonymize.py" \
  "06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01"
```

生成：

- `_blind/`：只给 Judge / 人工；
- `_controller/blind_map.json`：仅 Controller 可看。

**此时不要打开 blind_map.json。**

## Phase 7｜两个独立 Judge

分别启动 Judge-1、Judge-2 新会话。

他们只能读取：

- `05_Skills与自动化/B09_原著蒸馏Benchmark/JUDGE.md`
- `_blind/` 中匿名输出。

不得读取：

- Runner Pack 的身份说明；
- run_metadata；
- blind_map；
- 其他 Judge 的结果。

Judge 结果分别写：

```text
_local_runs/round-01/_judge-1/
_local_runs/round-01/_judge-2/
```

## Phase 8｜形成待人工盲评包

不要让人工读全部 12 组长文。

Controller 从 Judge 结果中抽取：

- 每个 sample 的匿名排序；
- 每个匿名方案最强 1–2 张机制卡；
- 争议最大的机制卡；
- Judge-1/Judge-2 分歧最大的项目。

形成一个 `human_pairwise_packet.md`，仍保持匿名。

人工只回答：

1. 哪张机制卡对原创最有用？
2. 哪张最像漂亮空话？
3. 哪个方案更能让我设计新故事，而不是理解原作？
4. 若只能保留一个机制，会保留哪个？

## Phase 9｜暂停点

完成人工盲评包后暂停。

向用户汇报：

- 样本已冻结；
- 12 组是否完成；
- 两 Judge 是否一致；
- 当前有哪些匿名候选明显领先/落后；
- 请求用户完成少量人工成对盲评。

**在用户完成人工盲评前，不揭盲。**

## Phase 10｜人工完成后才揭盲

揭盲后生成第一轮最终结论：

- 各维度冠军；
- 不选单一总冠军；
- 哪些上游能力直接借鉴；
- 哪些需二次改造；
- 哪些只保留为 Benchmark；
- C 候选有哪些假设被证伪；
- 第二轮迁移测试应该测试哪些 PATTERN。

只有通过跨作品迁移测试的机制，才进入 `04_写作知识库` 候选。
