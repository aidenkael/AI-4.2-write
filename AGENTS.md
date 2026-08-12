# AI-write Agent 长期规则

> 目标：让复杂后台服务作者，而不是让作者服务系统。

## 1. 当前阶段

**当前唯一主线：单书蒸馏成品化。**

G0–G4 已关闭。G5｜正文诊断与修订最小闭环：**PAUSED**。不得继续要求作者评价 G5 测试正文。

开始任务前读：目录说明、AGENTS、长期手册、当前索引、项目记忆、阶段门禁和当前专项文件。

## 2. 当前用户体验目标

用户只指定一本书并发起一次“蒸馏这本书”的任务。

Agent 应尽量独立完成：

`书名/book_id → SourcePrepare 状态判断 → BookDistill → BKP Finalize → Retrieval 可发现 → 简短报告`

不要让作者手动执行内部命令、选择 Deep Dive、维护 evidence 或检查 Schema。

## 3. SourcePrepare 边界

SourcePrepare 只做输入标准化，不做文学分析。

- 已有 PASS：直接复用；
- 没有输出：运行单书 SourcePrepare；
- REVIEW/FAIL：停止并报告原因，只有确实需要人工选源/补素材时再询问作者；
- 不覆盖、不修改 `01_原始素材`。

## 4. BookDistill 内部方法

当前方法保持：

1. Base Scan；
2. 至少两个互补 Discovery Pass：长篇运行/读者动力、Reader/Page Craft；
3. BookProfile；
4. 0～N 个按需 Deep Dive；
5. 总编辑式回源核证与 Finalize；
6. BKP 校验。

Deep Dive 次数不固定。《一九八四》《三体》各 3 次专项只是历史验证样本。

“Pass”是分析目标，不等于单次模型调用。长书可分章/分块，结果落盘后跨章收敛。

BookProfile 是导航，不是过滤器；原著始终是最高事实源。

## 5. BKP 边界

BKP 长期保留作品身份、作品地图、BookProfile、Observation、重要 Inference、Work-specific Pattern、Deep Dive 最终知识，以及可追溯 Evidence / scope / boundary / counterevidence / confidence。

单书 BKP 不自动升级为普遍写作规则。

作者默认只先看到 BookProfile、最值得调用的创作问题和简短完成报告；后台详细知识按需检索。

## 6. 当前开发任务

优先复用现有 SourcePrepare / BookDistill；只补：

- 单书 orchestrator / runbook；
- 阶段状态判断；
- Deep Dive 选择与记录；
- 失败报告；
- 必要的中断恢复；
- 新书端到端验收。

除真实阻塞外，不重写稳定核心，不扩张 Schema。

## 7. 当前禁止

- 不继续 G5 正文诊断/修订实验；
- 不要求作者阅读测试小说；
- 不批量蒸馏全部素材；
- 不固定每本书相同 Deep Dive 次数；
- 不升级 Retrieval/RAG/KG；
- 不开发 Writer/Reader/Editor/Controller/UI/大型数据库/多 Agent 平台；
- 不因为单本书一个特殊问题扩张长期架构。

## 8. Git 安全

无明确授权禁止：`reset / restore / clean / force push / rebase / merge`。

未知或历史 local dirty / untracked / `stash@{0}` 不清理、不覆盖、不自动 pop/drop。普通同步保持单一 `main`，不要为了临时保护留下无意义长期分支。

## 9. 当前验收标准

选一部此前未蒸馏的新书；用户只启动一次；Agent 从 SourcePrepare 状态判断开始独立跑到最终 BKP，校验通过且 KnowledgeRetrieve 可发现。

专项入口：`06_工作区/单书蒸馏成品化_当前目标.md`。
