# B09 Round 01 Status

- 状态：`PILOT_COMPLETE_FORMAL_RERUN_REQUIRED`
- 更新时间：2026-08-09
- 当前阶段：样本冻结完成；单窗口 pilot 已完成并通过结构检查，但因运行粒度与会话隔离偏差，不进入正式盲审。正式 Round 01 需要按原始协议重跑 12 个独立双窗口 Runner。

## 已完成

- [x] Benchmark 总设计
- [x] B09 第一轮执行协议
- [x] 3 样本 × 2 窗口冻结规则
- [x] D0 / A / B / C 四 Runner 协议
- [x] Evidence / Interpretation / Mechanism Card 统一合同
- [x] 样本 SHA256 / 章节边界冻结器
- [x] Runner 输出确定性检查器
- [x] 匿名化工具
- [x] Blind Judge 协议
- [x] 本地 Agent 完整执行任务
- [x] 本地 manifest / run 目录加入 `.gitignore`
- [x] Phase 1：检查本地来源并筛除明显污染样本
- [x] Phase 2：冻结 WN-A / WN-B / WL-A 三个样本
- [x] Controller sanity check：窗口、覆盖声明、非重叠与源文件保护通过
- [x] `06_工作区/SourcePrepare/` 加入 `.gitignore`
- [x] Pilot：3 作品 × 2 单窗口 × 4 Runner = 24 组完成
- [x] Pilot：24/24 deterministic structural check PASS
- [x] Pilot 偏差审计完成
- [x] 正式重跑决定已记录：`00_项目控制/B09_Round01_Pilot偏差与正式重跑决定.md`

## 第一轮冻结样本

### WN-A：《庆余年》

- 类别：网络小说
- 边界模式：chapter
- 探测章节：750
- OPENING：span 1–6
- MIDDLE：span 373–378

### WN-B：《道诡异仙》

- 类别：网络小说
- 边界模式：chapter
- 探测章节：1042
- OPENING：span 1–6
- MIDDLE：span 519–524

### WL-A：《一九八四》

- 类别：世界文学
- 来源：本地 SourcePrepare 派生干净文本；原始来源仍只读保留
- 边界模式：segment fallback
- 可用 segment：19
- OPENING：segment 1–6
- MIDDLE：segment 7–12
- 说明：六段 MIDDLE 窗口中心接近全文 segment 9.5–10，不需要重新冻结。

## Pilot 判定

已完成的 24 组输出保留为：

`round-01-pilot-single-window`

用途：

- 验证样本、冻结器、输出合同和结构检查器；
- 观察单窗口方法行为；
- 记录协议歧义和执行环境限制。

禁止：

- 不进入 Blind Judge；
- 不用于方法排名；
- 不用于人工赢家判断；
- 不据此决定采用哪个上游 Skill。

### 无效性来源 1：运行粒度

原始协议要求一个 Runner 对同一作品同时读取 OPENING + MIDDLE，再做跨窗口检查。Pilot 把两个窗口拆成独立运行，削弱了 A/B 的跨阶段验证能力。

### 无效性来源 2：会话隔离

Pilot 因 subagent 消息投递失败，改为同一会话顺序执行。虽然文件层未互读其他 Runner 输出，但不能排除方法提示和前序推理在会话中的串扰。

## 下一动作：正式 Round 01 Runner

正式运行必须新建目录，例如：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_runs/round-01-formal/`

正式规模：

`3 作品 × 4 Runner = 12 个独立运行`

每个运行一次同时读取该作品两个冻结窗口：

- OPENING
- MIDDLE

并只输出一套四文件合同 + metadata + check report。

### 正式有效性硬门槛

- 12 个 Runner 必须是独立新会话/独立 Agent 进程；
- 如果 subagent 不可用，可使用 12 个顺序启动但完全独立的新进程/新会话；
- 不允许再次降级到同一会话顺序扮演 D0/A/B/C；
- 如果执行环境做不到真正隔离，停止并汇报，不运行正式结果；
- 每次运行前核对 source SHA256；
- 只读取当前 sample 的两个冻结窗口；
- Runner 之间不得互读输出；
- 不读取 Judge；
- deterministic check 必须逐组执行；
- pilot 输出不得覆盖或混入正式结果。

## 当前阻塞

需要本地执行环境提供真正独立的新 Agent 会话/进程。是否可自动实现必须先做一个隔离探针，不通过则停止。

## 正式 12 组完成后的下一状态

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`
