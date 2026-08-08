# B09 Round 01 Status

- 状态：`CLI_PROCESS_PROBE_PASS_PREFLIGHT_V2_REQUIRED`
- 更新时间：2026-08-09
- 当前阶段：样本冻结完成；单窗口 pilot 已完成但不进入正式评审；subagent 隔离失败后已改用 `codex exec` 独立 OS 进程，Probe-X / Probe-Y 隔离通过。正式 12 组运行前需完成 CLI Preflight v2，以排除仓库读取范围和全局 Skill/插件污染。

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
- [x] 本地 manifest / run 目录加入 `.gitignore`
- [x] Phase 1：筛选并检查本地来源
- [x] Phase 2：冻结 WN-A / WN-B / WL-A
- [x] Controller sanity check
- [x] `06_工作区/SourcePrepare/` 加入 `.gitignore`
- [x] Pilot：3 作品 × 2 单窗口 × 4 Runner = 24 组完成
- [x] Pilot：24/24 deterministic structural check PASS
- [x] Pilot 偏差审计：单窗口粒度 + 同会话串扰风险
- [x] 正式重跑决定记录
- [x] subagent 隔离探针失败并按协议停止
- [x] `codex exec` 独立 OS 进程隔离探针 PASS
- [x] 固定 CLI：`codex-cli 0.147.0-alpha.6.5`
- [x] 固定模型：`deepseek-v4-flash`
- [x] 固定 reasoning effort：`high`
- [x] CLI 隔离审核与正式运行放行条件已记录：`00_项目控制/B09_CLI隔离审核与正式运行放行条件.md`

## 第一轮冻结样本

### WN-A：《庆余年》
- 边界模式：chapter
- 探测章节：750
- OPENING：span 1–6
- MIDDLE：span 373–378

### WN-B：《道诡异仙》
- 边界模式：chapter
- 探测章节：1042
- OPENING：span 1–6
- MIDDLE：span 519–524

### WL-A：《一九八四》
- 边界模式：segment fallback
- 可用 segment：19
- OPENING：segment 1–6
- MIDDLE：segment 7–12
- 六段 MIDDLE 窗口中心接近全文 segment 9.5–10，不重新冻结。

## Pilot 定位

现有 24 组只作为工程 pilot：

- 验证样本、冻结器、合同、checker；
- 不进入 Blind Judge；
- 不用于方法排名；
- 不用于最终 Skill 采用决策。

## CLI 隔离审核结论

独立 OS 进程机制本身已通过 Probe，但不能仅依赖 `-C + workspace-write` 声称 Runner 只能读取 cwd。正式执行改为：

- 专用最小 Benchmark CODEX_HOME；
- 仓库外空临时 cwd；
- stdin 直接注入当前 Runner 方法 + 双窗口正文 + 必要 manifest；
- 优先 read-only sandbox；
- stdout 固定 envelope；
- Controller 拆分 stdout 后写回 Local Only 正式目录；
- 正式 12 组启动前随机冻结执行顺序。

详见：

`00_项目控制/B09_CLI隔离审核与正式运行放行条件.md`

## 当前下一动作：Preflight v2

本地 Agent 同步 `main` 后执行：

`06_工作区/01_待处理/B09_原著蒸馏Benchmark/README_正式Round01重跑任务.md`

先完成 Preflight v2：

1. 建立专用最小 CODEX_HOME；
2. 在仓库外空 cwd 启动 `codex exec --ephemeral`；
3. 固定 `deepseek-v4-flash` + reasoning high；
4. 优先 read-only；
5. stdin 输入短测试；
6. stdout 返回固定 envelope；
7. 确认没有依赖仓库文件、全局写作 Skill、插件或历史会话。

若 Preflight v2 PASS，可直接继续正式 12 组，无需再次等待 Controller。

若 FAIL，立即停止并汇报，不自行扩大权限或回退共享会话。

## 正式 Round 01 规模

`3 作品 × 4 Runner = 12 个独立运行`

每个 Runner 一次同时处理该作品 `OPENING + MIDDLE` 两个窗口。

正式 Runner 启动前一次性随机生成并冻结 12 组执行顺序，以降低不可见服务端模型漂移造成的固定顺序偏差。

## 正式 12 组完成后的下一状态

`FORMAL_RUNNERS_COMPLETE_READY_FOR_BLINDING`
