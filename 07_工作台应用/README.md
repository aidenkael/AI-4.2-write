# 07_工作台应用

Go Write 正式作者侧桌面应用。`PRODUCT_BASELINE = GO_WRITE_2_0_APPROVED`；UI 1.0 仅保留为历史技术纵切/实现参考。当前阶段：`REAL_WRITING_USAGE`。

## 当前状态（2026-09-01）

- M1–M4 真实运行时纵切已完成并合并至 main：NewProject、StoryPlan、StoryWrite、Foundation 设计与 Review 均有当前正式路径。
- Agent 任务按既有任务合同走 Interactive `/gowrite` 或已配置的 Direct 路径；Daily AI 是独立、薄的 Direct-AI 路径，不取代需要工具/多步骤决策的 Agent。
- 最新前瞻规则：作者编辑立即保存；保存不调用 AI；例行语义整合只能由作者显式「更新作品状态」触发。该 runtime/UI 迁移已批准但尚未实现。

## 逻辑结构

```text
07_工作台应用/
├─ desktop/      # pywebview 桌面外壳
├─ ui/           # React + TypeScript + Vite
└─ backend/
   ├─ bridge/
   ├─ operations/
   ├─ agents/
   ├─ views/
   └─ config/
```

## 职责边界

```text
UI → Bridge → Author Operations → Code / Direct AI / Agent Adapter / Task Manager → 现有 Skills → 正式项目/知识数据
```

- UI 禁止直接调用 StoryWrite、StoryPlan、BookDistill 等 Skill。
- UI 禁止直接修改 Story State 或正式正文。
- Agent 禁止绕过作者确认修改 production authority。
- views 只负责「正式状态 → UI 展示数据」，不能拥有第二套故事事实。
- 作者对正文 / Story State 的修改必须走既有 authority / writeback 合同
  （accepted prose → ProjectWorkspace → settlement → Story State）。

## 技术路线（UI 1.0）

| 层 | 选型 |
|---|---|
| 桌面壳 | pywebview |
| 前端 | React + TypeScript + Vite |
| UI 基础组件 | shadcn/ui |
| 正文编辑 | CodeMirror 6 |
| 故事地图 | Cytoscape.js |
| 异步任务状态 | Python Task Manager；前端需要时使用 TanStack Query |
| 长列表 | 需要时使用 TanStack Virtual |
| 密钥 | Python keyring / OS credential storage |
| Windows 打包 | PyInstaller |
| 现有后台 | 继续使用现有 Python Skills |

AI-write 自研主要集中：Author Operations、Agent Adapter、Bridge、Task Manager、UI Views。

## 1.0 明确暂不建设

Electron、Tauri/Rust、FastAPI、WebSocket、Redis、Celery、Neo4j、自研 UI 组件库、
自研正文编辑器、自研关系图画布、原创全文向量数据库/RAG、复杂工作流节点编辑器、
多人协作、云账户、统一真实费用核算、AI 图片生成系统、固定总章数/目标字数、
复杂写作统计仪表盘。

统一表述：当前无真实需求证据，1.0 不建设；未来由真实 consumer blocker 决定。

## 运行

前置：Python 3；Windows WebView2 Runtime（已安装）；Node.js + npm。

> **依赖一律使用根目录 venv：`E:\AI-Write\.venv`**（已被 .gitignore 排除，不入库）。
> 安装与启动都请优先使用该 venv 的 Python，**不要用全局 Python**，避免污染全局环境。
> 若 `.venv` 尚不存在，先执行：`python -m venv E:\AI-Write\.venv`。

```powershell
# 0) 首次：创建根目录 venv（已存在则跳过）
python -m venv E:\AI-Write\.venv

# 1) Python 依赖（一律用 venv 的 Python）
E:\AI-Write\.venv\Scripts\python.exe -m pip install -r desktop/requirements.txt

# 2) 前端依赖
cd ui
npm install

# 3) 构建前端（产物 ui/dist/）
npm run build

# 4) 启动桌面（默认加载构建产物，用 venv 的 Python）
cd ..
E:\AI-Write\.venv\Scripts\python.exe desktop/main.py
```

开发模式（前端热更新）：

```powershell
# 终端 1
cd ui
npm run dev          # Vite dev server，默认 http://127.0.0.1:5173

# 终端 2（用 venv 的 Python）
E:\AI-Write\.venv\Scripts\python.exe desktop/main.py --dev
```

Bridge 链路：React 唯一入口 `ui/src/bridge/client.ts` ↔ `desktop/main.py` 注册的
`AppApi`（`backend/bridge/app_api.py`）。统一返回合同 `{ok, data, error}`；
当前已暴露真实作品浏览、设置、新建作品、故事规划、正文写作、作品地基设计与检查等方法。

## Qoder 桥（Go Write 管长期记忆，Qoder 只执行当前任务）

Agent 执行可按既有任务合同使用 Qoder Desktop `/gowrite` 或已配置的 Direct 路径；Daily AI 则使用独立、薄的 Direct-AI 调用。无论路径如何，Go Write 仍持有项目 authority 与 Context，模型/Agent 均不得绕过验证和作者确认合同。

- Go Write 侧：Interactive Agent 请求（如 `prepare_new_project` / `prepare_story_plan`）生成唯一 `request_id`
  + 保存完整 Agent task + 指定结果写回位置（`06_工作区/应用开发/.qoder_bridge/`，
  Local Only，可删除）；对应的 `get_*_request` 轮询写回结果，校验 `request_id`
  后把模型最终结果交回现有严格 JSON/字段验证与 StoryDesign / StoryPlan。
- Qoder 侧：用户级自定义命令 `~/.qoder/commands/gowrite.md`（官方 Custom
  Command；模板见 `06_工作区/应用开发/.qoder_bridge/gowrite.md.template`）。
  Qoder 读 `active.json` → 读请求文件 → 按 `task` 执行 → 只向该请求指定的
  `response_path` 写回（必须携带相同 `request_id`）→ 给用户一句完成提示。
- 安全：`request_id` 防串任务；取消/超时/完成后清理桥文件，旧结果不可能被
  下一次请求接受；桥文件绝不在 03_作品工程 中；Qoder 会话历史不是记忆来源。
- 已接入当前路径的作者链包括新建作品、故事规划、正文写作、Foundation 设计与检查；每项任务按其既有 Interactive/Direct 合同执行。

## 运行规则

- 正式代码禁止依赖 `06_工作区/应用开发/` 中任何临时文件。
- 现有冻结 Skill（MaterialIntake / SourcePrepare / BookDistill / KnowledgeRetrieve /
  ProjectWorkspace / StoryDesign / StoryPlan / ContextCompiler / StoryWrite）
  不迁移、不修改；07 通过 Agent Adapter 调用。
- 不建立全局 `current_project` authority；多项目 authority 隔离保持。
