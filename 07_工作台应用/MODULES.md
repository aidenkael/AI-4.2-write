# Go Write 工作台代码模块规划

> 状态：APPROVED_DESIGN  
> 原则：先分职责，再按真实修改逐步迁移；不做一次性目录大搬家。

## 1. 目标

当前 `07_工作台应用` 已有大量真实功能。后续维护采用少量稳定模块，避免继续把所有业务堆进 `backend/operations`，也避免为了架构整齐创建大量抽象层。

目标依赖方向：

```text
UI pages/features
    ↓
Bridge / public contracts
    ↓
Application use-cases
    ↓
Project authority/domain ── Knowledge/Context
    ↓                         ↓
Deterministic code      Direct AI / Agent+Skills
    ↓                         ↓
统一 validate / settlement / writeback
    ↓
03_作品工程 + 02/04 知识
```

任何层都不得绕过统一 authority 直接维护第二套人物、世界观、规划或正文状态。

## 2. Backend 目标模块

### A. `project/` —— 作品真相与 authority 核心

唯一职责：维护“这本小说现在是什么”。

当前逻辑归属：
- `project_model.py`
- `project_snapshot.py`
- `project_data.py`
- `project_impact.py`
- `author_edit.py`
- `change_settlement.py` 中**写回/authority/patch 应用**部分
- 章节正式保存与 accepted index 的确定性部分

长期 API 只围绕：
- load current project snapshot
- durable author edit
- validate/apply semantic patch
- accept/cancel candidate
- retire/restore domain object
- current/future/actual result projection

规则：这是唯一可写原创权威的模块；AI、Agent、UI 不直接碰底层文件。

### B. `ai/` —— Direct AI 薄通道

当前尚未正式实现；以后只在接独立 AI API 时建立。

最小文件建议：

```text
backend/ai/
├─ runner.py        # run_structured
├─ contracts.py     # request/result/schema 最小合同
└─ providers/       # 仅真实需要的 provider adapter
```

禁止在这里建立：memory、workflow、agent graph、知识库、项目状态。

第一批消费者候选：高频语义 settlement、章节实际摘要、人物/关系/世界状态增量提取。

### C. `agent/` —— Agent 与工具执行

唯一职责：执行需要工具/Skill/多步骤决策的任务。

当前逻辑归属：
- `backend/agents/*`
- `operations/agent_runner.py`
- `operations/qoder_bridge.py`
- `operations/execution_tasks.py`
- `operations/author_operation.py` 中 Agent/bridge 任务生命周期部分

Agent 不持有作品长期状态；任务结束后只返回 candidate/structured result。

### D. `creation/` —— 作者创作 Use Cases

唯一职责：把作者动作编排成一次业务用例，不持有第二份 authority。

建议按真实作者动作分文件，而不是按 AI 技术分文件：

```text
backend/creation/
├─ new_project.py
├─ planning.py
├─ writing.py
└─ review.py
```

当前逻辑来源：
- `new_project.py`
- `story_planning.py`
- `story_writing.py`
- `review.py`

Use Case 决定需要：Code / Direct AI / Agent+Skill 中哪一种；真正写回仍交给 `project/`。

### E. `knowledge/` —— 外部知识与 Context 接口

唯一职责：连接现有 05 Skills，不复制 Skill 实现。

建议只保留薄 adapter：
- KnowledgeRetrieve 调用；
- retrieval snapshot；
- ContextCompiler 调用；
- knowledge selection/package binding；
- provenance/fingerprint 校验。

当前逻辑归属：
- `retrieval_snapshot.py`
- StoryPlan/StoryWrite 中重复的 retrieval/context glue（未来触及时才抽）

`05_Skills与自动化` 仍是 Skill 真源；07 不复制 BookDistill/MethodDistill/KnowledgeRetrieve 业务规则。

### F. `materials/` —— 素材生命周期

当前 `operations/materials.py` 已超过普通薄 use-case 规模。后续真实修改时按职责逐步拆分，不一次搬家：

```text
backend/materials/
├─ catalog.py
├─ intake.py
├─ prepare.py
└─ distill.py
```

实际核心仍复用 `MaterialIntake / SourcePrepare / BookDistill / MethodPrepare / MethodDistill`，应用层只做作者操作编排与状态投影。

### G. `infra/` —— 应用基础设施

只放与小说语义无关的横切能力：
- Settings/config；
- execution audit；
- desktop/bridge transport；
- runtime/build fingerprint；
- OS credential；
- 通用错误/日志。

不得把人物/规划/世界观逻辑放进 infra。

## 3. Bridge 边界

`backend/bridge/app_api.py` 和 `ui/src/bridge/client.ts` 是前后端公开合同，不成为业务逻辑仓库。

规则：
- Bridge 做参数校验、类型/合同转换和调用；
- 不在 Bridge 推断文学语义；
- 前端收到的 project data 在共享边界统一 validate/normalize；
- 一个业务操作只暴露一个正式入口，避免 legacy 双路径。

## 4. Frontend 模块

前端继续采用 feature-first，不另造 Redux/复杂状态框架。

稳定 feature：

```text
ui/src/features/
├─ projects/       # 正式 project identity/shell
├─ foundation/     # Story Bible 源编辑
├─ planning/       # future planning / fine outline
├─ writing/        # 正文与章节工作
├─ storyMap/       # 纯派生图/时间/线索
├─ review/         # advisory diagnostics
├─ materials/      # 素材与学习
├─ ideas/          # 灵感箱
├─ settings/       # AI/Agent/API 配置与审计入口
└─ tasks/          # 只管理真正 Agent/长任务的 UI 生命周期
```

共享层只保留：
- `components/`：无领域 ownership 的复用 UI；
- `contracts/`：稳定 UI/Bridge 类型；
- `bridge/`：网络/pywebview 调用；
- `layouts/`：布局；
- `assets/`：静态资产。

规则：
- 页面只组合 feature，不自行保存第二份业务状态；
- Foundation 与 Story Map 共用同一 editor/author presentation；
- Story Map 永远是派生视图；
- AppStore 只保留导航/toast/dialog/UI preference，不回流成业务 store；
- Direct AI 的轻量后台状态不强迫进入全局 AuthorTaskCoordinator；只有真正长任务/Agent任务才进入全局任务面。

## 5. 统一调用路由

未来所有新功能先分类：

```text
DETERMINISTIC
  → project/knowledge/materials 中代码执行

SEMANTIC_SINGLE_CALL
  → ai.run_structured(...)
  → project.validate/apply

TOOL_WORKFLOW
  → agent.run(...)
  → existing Skills/tools
  → project.validate/apply

AUTHOR_DECISION
  → candidate
  → author confirm
  → project.writeback
```

不要建立第五种执行路径。

## 6. 新书重大基座的模块协作

```text
creation/new_project or planning
  ↓
project.snapshot
  ↓
Agent：拆 knowledge_needs / 多步研究
  ↓
knowledge.KnowledgeRetrieve（多轮、每轮少量）
  ↓
Agent：综合人物/世界/关系/system/结构候选
  ↓
作者确认
  ↓
project.author_edit / confirm / writeback
  ↓
统一 Snapshot 刷新
```

不新增 WorldBuilder Agent、Character Agent 或 PowerSystem Skill。

## 7. 高频正文同步的模块协作

目标迁移方向：

```text
正文 durable save
  ↓
project.diff
  ↓
Direct AI：一次结构化语义抽取
  ↓
project.validate semantic patch
  ↓
机械确定项自动写回
歧义/创作项 → 作者确认
  ↓
Snapshot / Story Map / next Context 刷新
```

这样人物摘要、关系变化、事件、时间、伏笔、世界状态不会占用 Agent `/gowrite` 单任务槽。

## 8. 迁移策略：Move on touch

当前不执行大规模移动。以后每个真实任务只遵守：

1. 新文件进入目标模块；
2. 修改旧大文件时，如果能在不扩大任务的情况下自然抽出一个完整职责，则抽出；
3. 无真实修改需求的旧文件不为目录整齐搬迁；
4. 不允许“新目录 + 老目录各保留一套实现”；
5. 一次迁移后立即删除旧实现/旧入口；
6. public contract 变化必须有最小聚焦测试；
7. 模块边界测试优先于大量重复测试。

## 9. 当前最值得做、但不在本次文档任务中实施的代码顺序

1. 先完成当前作者 runtime 验收暴露的 UI 可达性、退役恢复等确定性问题；
2. 接入最薄 Direct AI runner；
3. 只把 `change_settlement` 的高频轻语义执行从 Agent 迁到 Direct AI，保持 settlement/writeback 合同不变；
4. 新书重大基座设计继续由 Agent + KnowledgeRetrieve 承载，并验证多轮知识调用质量；
5. 根据真实使用再判断 StoryPlan/StoryWrite/Review 哪些子任务值得迁 Direct AI；不预先重写全部。

## 10. 明确不做

- 不引入 Dify/LangChain/LlamaIndex/AutoGen 作为 Go Write runtime；
- 不建 LangGraph/自研工作流图；
- 不建 multi-agent 系统；
- 不建第二状态数据库；
- 不建 Character/World/Relationship 独立同步服务；
- 不复制 05 Skills 到 07；
- 不因为文件大就机械拆文件；
- 不为了“模块化”增加无业务价值的 interface/factory/service/repository 层。

判断标准始终是：**是否让下一次真实维护更简单，同时不增加作者侧复杂度和模型消耗。**