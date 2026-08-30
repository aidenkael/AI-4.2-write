/**
 * AI-write 唯一 Bridge 客户端。
 *
 * 规则：React 组件禁止直接调用 `window.pywebview.api`；
 * 所有 Python 调用必须经过本模块。Python 侧唯一暴露入口：
 * `07_工作台应用/backend/bridge/app_api.py`（AppApi）。
 *
 * 统一返回合同（与 AppApi 一致）：
 *   成功：{ ok: true,  data: T,    error: null }
 *   失败：{ ok: false, data: null, error: { code, message } }
 */

export class BridgeError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'BridgeError'
    this.code = code
  }
}

export interface AppStatusData {
  app_name: string
  status: string
  message: string
}

export interface ProjectItem {
  project_id: string
  name: string
}

export interface ProjectOverview {
  project_id: string
  name: string
  work_direction?: string
  reader_promise?: string
  current_plans?: Array<{ id: string; description: string }>
  state: {
    state_rev: number
    last_authority_source: string
  }
  last_accepted?: {
    chapter_path: string
    scene_ref: string
    sequence: number
  }
  recent_prose?: {
    scene_ref: string
    window_chars: number
    below_target: boolean
  }
  planning?: {
    entries: number
    latest: string | null
    latest_id?: string
    latest_occurred?: boolean
  }
  progress?: {
    current_chapter: number
    actual_words: number
    target_words: number | null
  }
  settlement?: SettlementSummary
}

interface ApiResult<T> {
  ok: boolean
  data: T | null
  error: { code: string; message: string } | null
}

/**
 * 等待 pywebview Bridge 就绪。
 *
 * pywebview 的 `window.pywebview.api` 在页面导航完成后才注入，早于 React 首次
 * useEffect 执行；这里监听 `pywebviewready` 事件并以 100ms 轮询兜底，超时报错。
 * 在普通浏览器（无 pywebview）中同样会超时报错，UI 显示 Bridge 错误而非静默失败。
 */
function whenBridgeReady(timeoutMs = 10000): Promise<any> {
  return new Promise((resolve, reject) => {
    const w = window as any
    let settled = false

    const cleanup = () => {
      window.clearTimeout(timer)
      window.clearInterval(poll)
      w.removeEventListener?.('pywebviewready', onReady)
    }
    const onReady = () => {
      if (settled) return
      const api = w.pywebview?.api
      if (!api) return
      settled = true
      cleanup()
      resolve(api)
    }
    const onTimeout = () => {
      if (settled) return
      settled = true
      cleanup()
      reject(new BridgeError('BRIDGE_TIMEOUT', 'pywebview bridge 就绪超时：请通过 desktop/main.py 启动应用'))
    }

    const timer = window.setTimeout(onTimeout, timeoutMs)
    const poll = window.setInterval(onReady, 100)
    w.addEventListener?.('pywebviewready', onReady)
    onReady() // 已注入则立即 resolve
  })
}

/** 统一调用：解析 {ok, data, error} 合同；失败抛 BridgeError。 */
async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  const api = await whenBridgeReady()
  const result = (await api[method](...args)) as ApiResult<T>
  if (!result || result.ok !== true || result.data === null) {
    const err = result?.error
    throw new BridgeError(
      err?.code ?? 'BRIDGE_INVALID_RESPONSE',
      err?.message ?? `${method} 返回异常`,
    )
  }
  return result.data
}

/** 获取应用状态（骨架验证用；数据来自 Python AppApi.get_app_status）。 */
export async function getAppStatus(): Promise<AppStatusData> {
  return call<AppStatusData>('get_app_status')
}

/** 真实作品列表（来自 03_作品工程）。 */
export async function listProjects(): Promise<ProjectItem[]> {
  const data = await call<{ projects: ProjectItem[] }>('list_projects')
  return data.projects
}

/** 打开作品（以 project_id 优先，或作品名）。 */
export async function openProject(project: { project_id?: string; name?: string }): Promise<{ project_id: string; name: string }> {
  return call<{ project_id: string; name: string }>('open_project', project)
}

/** 作品最小概览（只读正式状态）。 */
export async function getProjectOverview(projectId: string): Promise<ProjectOverview> {
  return call<ProjectOverview>('get_project_overview', projectId)
}

// ---------------- Agent / 模型 / Token 设置 ----------------

export type ExecutionMode = 'interactive_bridge' | 'direct'

export interface DiscoveredModel {
  id: string
  display_name: string
  selectable: boolean
  selected?: boolean
  provider_id?: string | null
  model_id?: string | null
  source?: 'native' | 'custom'
}

export interface InteractiveEnvironment {
  available: boolean
  bridge_ready: boolean
  command_name: string
  command_ready: boolean
  relevant_status?: Record<string, string | null>
  repair_hint?: string | null
}

export interface ProviderModelGroup {
  provider_id: string
  display_name: string
  models: DiscoveredModel[]
}

export interface DirectEnvironment {
  available: boolean
  auth_status: string
  model_selection: 'selectable' | 'managed' | 'none'
  models: DiscoveredModel[]
  custom_models: DiscoveredModel[]
  /** 按 provider 分组的可选手目录（通用解析；不硬编码任何 provider/model 名）。 */
  provider_models?: ProviderModelGroup[] | null
  managed_model?: { id: string; display_name: string; provider_id?: string | null } | null
  capabilities: Record<string, unknown>
}

export interface DesktopEnvironment {
  installed: boolean
  status: string
  path: string | null
  launcher_path: string | null
  version: string | null
  error?: string | null
}

export interface CliEnvironment {
  detected: boolean
  usable: boolean
  status: string
  kind: string
  path: string | null
  resolved_command: string[]
  version: string | null
}

export interface AgentEnvironment {
  agent_id: string
  display_name: string
  installed: boolean
  available: boolean
  version: string | null
  errors: string[]
  desktop?: DesktopEnvironment
  cli?: CliEnvironment
  interactive: InteractiveEnvironment
  direct: DirectEnvironment
}

export interface AgentSettings {
  default_execution_mode: ExecutionMode
  interactive_agent: string
  direct_agent: string
  direct_model: string | null
  direct_custom_model: string | null
}

export interface AgentSettingsData {
  settings: AgentSettings
  agents: AgentEnvironment[]
  /** 本机发现的来源：cache = 复用上次检测快照；fresh = 本次刚执行发现。 */
  discovery?: {
    source: 'cache' | 'fresh'
    discovered_at: string | null
  } | null
}

export interface ConnectionTestResult {
  agent: string
  status: 'ok' | 'failed' | 'not_configured'
  message: string
  output?: string | null
}

/** 当前设置 + 各 Agent 状态/能力 + BYOK Token 是否已配置（无明文）。 */
export async function getAgentSettings(): Promise<AgentSettingsData> {
  return call<AgentSettingsData>('get_agent_settings')
}

/** 显式“重新检测”：强制刷新本机 Agent/模型目录并更新后端 last-known 快照。 */
export async function discoverAgents(): Promise<{
  agents: AgentEnvironment[]
  discovery: AgentSettingsData['discovery']
}> {
  return call<{ agents: AgentEnvironment[]; discovery: AgentSettingsData['discovery'] }>('discover_agent_environment')
}

/** 保存普通设置（不含 Token）。 */
export async function saveAgentSettings(settings: Partial<AgentSettings>): Promise<{ settings: AgentSettings }> {
  return call<{ settings: AgentSettings }>('save_agent_settings', settings)
}

/** 在官方 Qoder CN 命令位置安装/修复唯一 Go Write 命令定义。 */
export interface InteractiveRepairResult {
  installed_paths: string[]
  command_ready: boolean
  status: 'installed' | 'restart_required' | 'error'
  restart_required: boolean
  errors: string[]
}

export async function installOrRepairInteractiveCommand(agent: string): Promise<InteractiveRepairResult> {
  return call<InteractiveRepairResult>('install_or_repair_interactive_command', { agent })
}

/** 测试连接（无副作用任务 + 临时目录）；BYOK 未配置 Token 时返回 not_configured。 */
export async function testAgentConnection(payload: {
  agent: string
  model?: string | null
  custom_model?: string | null
}): Promise<ConnectionTestResult> {
  return call<ConnectionTestResult>('test_agent_connection', payload)
}

// ---------------- 新建作品（"我有个想法"纵切） ----------------
// Go Write 只准备任务（pending request）；模型执行由作者在 Qoder 桌面端
// 输入 /gowrite 完成；前端轮询写回结果，出现候选后由作者确认。

export interface StoryCandidate {
  work_direction: string
  proposal: string
  reader_promise: string
  hard_constraints: string[]
  open_space: string[]
  unknowns: string[]
}

export interface ProposeResult {
  proposal_token: string
  project_id: string
  name: string
  status: string
  candidate: StoryCandidate
  execution?: Record<string, unknown>
  message: string
}

export interface PrepareNewProjectResult {
  request_id: string
  name: string
  status: string
  execution_mode?: string
  agent_id?: string | null
  model?: string | null
  message: string
}

export interface NewProjectRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  result?: ProposeResult | null
  error?: string | null
}

export interface ConfirmResult {
  project_id: string
  name: string
  project_dir: string
  state_rev: number | null
  approved_direction_registered: boolean
  warning: string | null
  message: string
}

/** 我有个想法 → Go Write 准备本轮 Agent 任务（不运行模型），返回 request_id。 */
export async function prepareNewProject(payload: { name: string; idea: string }): Promise<PrepareNewProjectResult> {
  return call<PrepareNewProjectResult>('prepare_new_project', payload)
}

/** 轮询 Qoder 写回结果：pending 继续等；completed 时 result 含候选。 */
export async function getNewProjectRequest(requestId: string): Promise<NewProjectRequestStatus> {
  return call<NewProjectRequestStatus>('get_new_project_request', { request_id: requestId })
}

/** 取消等待：旧结果不可能再被接受。 */
export async function cancelNewProjectRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_new_project_request', { request_id: requestId })
}

/** 作者明确确认 → 用后台保存的候选创建正式作品。 */
export async function confirmNewProject(payload: { proposal_token: string }): Promise<ConfirmResult> {
  return call<ConfirmResult>('confirm_new_project', payload)
}

// ---------------- 故事规划（"一起往前想"纵切） ----------------
// 双执行模式（由已保存 Settings 决定，UI 不分支 Agent/模型）：
// - Interactive：Go Write 准备任务 → Qoder 桌面端 /gowrite → 结果返回（pending 等待）；
// - Direct：Go Write 通过配置的 Agent/模型后台执行（prepare 立即返回，可轮询/取消）。
// 两种模式共用同一请求生命周期与同一严格 finalize。确认前只写临时 planning
// 工作区；只有作者明确确认（带后台 planning token）才写入正式 approved_plan。

export interface StoryPlanCandidate {
  proposal: string
  planning_items: string[]
  planning_projection?: PlanningProjection
}

export interface PlanningProjection {
  characters: Array<Record<string, unknown>>
  relationships: Array<Record<string, unknown>>
  settings: Array<Record<string, unknown>>
  storylines: Array<Record<string, unknown>>
  events: Array<Record<string, unknown>>
  foreshadowing: Array<Record<string, unknown>>
  chapter_changes: Array<Record<string, unknown>>
}

export interface ProposeStoryPlanResult {
  planning_token: string
  project_id: string
  name: string
  status: string
  candidate: StoryPlanCandidate
  execution?: Record<string, unknown>
  message: string
}

export interface ConfirmStoryPlanResult {
  project_id: string
  name: string
  state_rev: number | null
  message: string
}

export interface PrepareStoryPlanResult {
  request_id: string
  project_id: string
  name: string
  status: string
  execution_mode?: string
  agent_id?: string | null
  model?: string | null
  message: string
}

export interface StoryPlanRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  result?: ProposeStoryPlanResult | null
  error?: string | null
}

/** 一起往前想 → 按已保存 Settings 准备本轮任务（Interactive 等待 /gowrite；Direct 后台执行），返回 request_id。 */
export async function prepareStoryPlan(payload: {
  project_id: string
  author_question: string
}): Promise<PrepareStoryPlanResult> {
  return call<PrepareStoryPlanResult>('prepare_story_plan', payload)
}

/** 轮询执行结果：pending（Interactive 等待 /gowrite 或 Direct 执行中）继续等；completed 时 result 含候选。 */
export async function getStoryPlanRequest(requestId: string): Promise<StoryPlanRequestStatus> {
  return call<StoryPlanRequestStatus>('get_story_plan_request', { request_id: requestId })
}

/** 取消/丢弃：终止运行中的 Direct adapter（如有）；已完成未确认候选经后端清理使 planning_token 失效。 */
export async function cancelStoryPlanRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_story_plan_request', { request_id: requestId })
}

/** 作者明确确认 → 用后台保存的候选写入正式 approved_plan。 */
export async function confirmStoryPlan(payload: {
  project_id: string
  planning_token: string
}): Promise<ConfirmStoryPlanResult> {
  return call<ConfirmStoryPlanResult>('confirm_story_plan', payload)
}

// ---------------- 正文写作（"这一段想写什么"纵切） ----------------
// 统一请求生命周期：prepare → 执行（Direct 后台两阶段 / Interactive 两次
// /gowrite 两阶段）→ 轮询 → 候选 → confirm
// Interactive 阶段状态机：pending_selection →（Stage 1 验收 + Context 编译）
// → pending_prose → completed / failed / canceled。

export interface PrepareStoryWriteResult {
  request_id: string
  project_id: string
  name: string
  status: string
  execution_mode: string
  phase?: string | null
  agent_id: string
  model: string | null
  message: string
}

export interface StoryWriteRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  phase?: string | null
  message?: string | null
  result?: ProposeStoryWriteResult | null
  error?: string | null
}

export interface ProposeStoryWriteResult {
  writing_token: string
  project_id: string
  name: string
  scene_ref: string
  chapter_number: number
  draft_text: string
  execution: Record<string, unknown>
  message: string
}

export interface ConfirmStoryWriteResult {
  project_id: string
  name: string
  chapter_path: string
  chapter_number: number
  scene_ref: string
  message: string
}

/** 这一段想写什么 → 按已保存 Settings 准备本轮任务（Direct 后台两阶段 / Interactive 两阶段 /gowrite）。 */
export async function prepareStoryWrite(payload: {
  project_id: string
  author_input: string
  chapter_number?: number
}): Promise<PrepareStoryWriteResult> {
  return call<PrepareStoryWriteResult>('prepare_story_write', payload)
}

/** 轮询执行结果：pending（含 phase 与作者提示）继续等；completed 时 result 含正文候选。 */
export async function getStoryWriteRequest(requestId: string): Promise<StoryWriteRequestStatus> {
  return call<StoryWriteRequestStatus>('get_story_write_request', { request_id: requestId })
}

/** 取消等待：终止运行中的 Direct adapter；旧结果不可能再被接受。 */
export async function cancelStoryWriteRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_story_write_request', { request_id: requestId })
}

/** 作者明确"保留这段" → accept_prose 写入正式 03_正文。 */
export async function confirmStoryWrite(payload: {
  project_id: string
  writing_token: string
}): Promise<ConfirmStoryWriteResult> {
  return call<ConfirmStoryWriteResult>('confirm_story_write', payload)
}

// ---------------- 正式写作面（WritingPage 只读 read model） ----------------
// 数据源：03_作品工程/<project>/03_正文 + accepted_text_index（唯一权威）。
// 绝不返回临时候选；绝无写副作用。

export interface StoryWriteChapter {
  chapter_number: number
  title: string
  content: string
  words: number
  scene_count: number
  content_sha256?: string
  accepted?: boolean
  fine_outline_ref?: string | null
  fine_outline?: Record<string, unknown>
}

export interface StoryWriteSurface {
  project_id: string
  name: string
  chapters: StoryWriteChapter[]
  active_chapter_number: number
  total_words: number
  settlement?: SettlementSummary
}

/** 获取正式已采用正文写作面（只读；按章排序，active = 最新已接受章）。 */
export async function getStoryWriteSurface(projectId: string): Promise<StoryWriteSurface> {
  return call<StoryWriteSurface>('get_story_write_surface', { project_id: projectId })
}

// ---------------- 灵感箱（真实本地收件箱，非权威、无模型） ----------------

export type IdeaKind = 'text' | 'link'

export interface IdeaItem {
  id: string
  content: string
  kind: IdeaKind
  created_at: string
  used_project_ids: string[]
}

/** 列出全部灵感（created_at 倒序）。 */
export async function listIdeas(): Promise<IdeaItem[]> {
  const data = await call<{ ideas: IdeaItem[] }>('list_ideas')
  return data.ideas
}

/** 新增一条灵感（kind: text|link）。 */
export async function createIdea(payload: { content: string; kind: IdeaKind }): Promise<IdeaItem> {
  const data = await call<{ idea: IdeaItem }>('create_idea', payload)
  return data.idea
}

/** 删除一条灵感（幂等）。 */
export async function deleteIdea(ideaId: string): Promise<{ deleted: string }> {
  return call<{ deleted: string }>('delete_idea', { idea_id: ideaId })
}

/** 可选：把一条灵感标记为已用于某作品（非权威）。 */
export async function markIdeaUsed(payload: { idea_id: string; project_id: string }): Promise<IdeaItem> {
  const data = await call<{ idea: IdeaItem }>('mark_idea_used', payload)
  return data.idea
}

// ---------------- 素材目录（真实 canonical catalog；仅显式动作） ----------------

export interface MaterialItem {
  id: string
  name: string
  type: string
  author: string
  tags: string[]
  notes: string
  purification_status: string
  knowledge_status: string
  file_count: number
  /** 作者面分组：usable（可用于写作）/ needs_organization（待整理）/ needs_update（需更新）。 */
  author_group: 'usable' | 'needs_organization' | 'needs_update'
  /** 写作时能否被知识检索调用（只有已定稿可用知识才为 true）。 */
  writing_callable: boolean
  why: string
  next_step: string
}

export interface MaterialInboxFile {
  path: string
  filename: string
  sha256: string
  suffix: string
  unsupported: boolean
  exact_duplicate_matches: string[]
  possible_existing_candidates: string[]
}

export interface MaterialIntakeResult {
  ok: boolean
  new_ids: string[]
  attached: string[]
  duplicates_removed: unknown[]
  reviews: string[]
  moves: unknown[]
  git_outcome: string
  git_warning: string | null
  message: string
}

/** 只读读取 canonical 素材 ledger 投影。 */
export async function listMaterials(): Promise<MaterialItem[]> {
  const data = await call<{ materials: MaterialItem[] }>('list_materials')
  return data.materials
}

/** 显式触发 MaterialIntake catalog refresh（确定性、无模型）。 */
export async function refreshMaterials(): Promise<{ assets: number; files: number; containers: number; message: string }> {
  return call('refresh_materials')
}

/** 只读扫描 00_待入库。 */
export async function scanMaterialInbox(): Promise<{ inbox: string; files: MaterialInboxFile[] }> {
  return call('scan_material_inbox')
}

/** 作者显式选择的入库决策（走 MaterialIntake 确定性 intake 事务）。 */
export async function applyMaterialIntake(plan: { items: unknown[] }): Promise<MaterialIntakeResult> {
  return call<MaterialIntakeResult>('apply_material_intake', { plan })
}

// ---------------- 素材工作流（导入 → 分类 → 提纯 → 蒸馏） ----------------

export interface PickFilesResult {
  supported: boolean
  paths: string[]
  message: string
}

export interface ImportedFile {
  path: string
  filename: string
  size: number
}

export interface SkippedFile {
  path: string
  reason: string
}

export interface ImportMaterialResult {
  inbox: string
  imported: ImportedFile[]
  skipped: SkippedFile[]
  message: string
}

export interface ClassifyMaterialResult {
  status: 'ready' | 'pending'
  request_id?: string | null
  plan: { items: unknown[] }
  ambiguous?: string[]
  agent_required?: boolean
  agent_used?: boolean
  message: string
}

export interface ClassifyRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  plan?: { items: unknown[] } | null
  message?: string | null
  error?: string | null
}

export interface SourcePrepareResult {
  asset_id: string
  status: string
  message: string
  output_tail?: string | null
}

export interface BookDistillResult {
  asset_id: string | null
  status: string
  request_id?: string | null
  output_dir?: string | null
  message: string
}

export interface BookDistillRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  result?: BookDistillResult | null
  message?: string | null
  error?: string | null
}

export interface MaterialDetail {
  id: string
  name: string
  type: string
  writing_callable: boolean
  why: string
  next_step: string
  stage: string
  purification_status: string
  knowledge_status: string
}

/** 本地文件选择（pywebview 原生对话框）。 */
export async function pickMaterialFiles(): Promise<PickFilesResult> {
  return call<PickFilesResult>('pick_material_files', {})
}

/** 把本地文件字节 stage 到 MaterialIntake 收件箱（00_待入库）。 */
export async function importMaterialFiles(files: Array<{ path: string }>): Promise<ImportMaterialResult> {
  return call<ImportMaterialResult>('import_material_files', { files })
}

/** Agent 辅助入库：scan → 确定性事实 → 仅对无法定论文件调一次 Agent。 */
export async function classifyMaterialInbox(): Promise<ClassifyMaterialResult> {
  return call<ClassifyMaterialResult>('classify_material_inbox', {})
}

/** 轮询交互式分类结果。 */
export async function getMaterialClassifyRequest(requestId: string): Promise<ClassifyRequestStatus> {
  return call<ClassifyRequestStatus>('get_material_classify_request', { request_id: requestId })
}

/** 取消交互式分类。 */
export async function cancelMaterialClassifyRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_material_classify_request', { request_id: requestId })
}

/** 对指定素材显式运行真实 SourcePrepare（确定性，无模型）。 */
export async function runSourcePrepare(assetId: string): Promise<SourcePrepareResult> {
  return call<SourcePrepareResult>('run_source_prepare', { asset_id: assetId })
}

/** 对 SourcePrepare PASS 素材显式运行真实 BookDistill。 */
export async function runBookDistill(assetId: string): Promise<BookDistillResult> {
  return call<BookDistillResult>('run_book_distill', { asset_id: assetId })
}

/** 轮询 Interactive 蒸馏结果。 */
export async function getBookDistillRequest(requestId: string): Promise<BookDistillRequestStatus> {
  return call<BookDistillRequestStatus>('get_book_distill_request', { request_id: requestId })
}

/** 取消 Interactive 蒸馏。 */
export async function cancelBookDistillRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_book_distill_request', { request_id: requestId })
}

/** 作者面通用「提纯」：UI 只传素材 id，后端按类型分派到 SourcePrepare / MethodPrepare。 */
export async function prepareMaterial(assetId: string): Promise<SourcePrepareResult> {
  return call<SourcePrepareResult>('prepare_material', { asset_id: assetId })
}

/** 作者面通用「蒸馏」：UI 只传素材 id，后端按类型分派到 BookDistill / MethodDistill。 */
export async function distillMaterial(assetId: string): Promise<BookDistillResult> {
  return call<BookDistillResult>('distill_material', { asset_id: assetId })
}

/** 通用蒸馏轮询（后端按桥请求 kind 分派 BookDistill / MethodDistill）。 */
export async function getMaterialDistillRequest(requestId: string): Promise<BookDistillRequestStatus> {
  return call<BookDistillRequestStatus>('get_material_distill_request', { request_id: requestId })
}

/** 通用蒸馏取消。 */
export async function cancelMaterialDistillRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_material_distill_request', { request_id: requestId })
}

/** 单素材作者面详情（写作时能否调用 / 阶段 / 下一步；零模型）。 */
export async function getMaterialDetail(assetId: string): Promise<MaterialDetail> {
  return call<MaterialDetail>('get_material_detail', { asset_id: assetId })
}

// ---------------- 作品地基 / 故事地图（只读正式 Story State 投影） ----------------

export interface ProjectDataEntry {
  id: string | null
  label: string
  record: unknown
  source_ref?: string | null
  source_kind?: string | null
  provenance?: string | null
  category?: string | null
  status?: 'current' | 'future'
  editable?: boolean
}

export interface ProjectDataSections {
  characters: ProjectDataEntry[]
  relationships: ProjectDataEntry[]
  canon_facts: ProjectDataEntry[]
  occurred_events: ProjectDataEntry[]
  open_threads: ProjectDataEntry[]
  foreshadowing: ProjectDataEntry[]
  storylines: ProjectDataEntry[]
  approved_plan: ProjectDataEntry[]
}

export interface SettlementChange {
  change_id: string
  source_kind: string
  status: 'pending' | 'failed' | 'awaiting_author' | 'synchronized'
  delta: Record<string, unknown>
  semantic?: { summary?: string; consequences?: Array<Record<string, unknown>> } | null
  error?: string | null
}

export interface SettlementSummary {
  status: 'synchronized' | 'pending' | 'failed'
  pending_count: number
  failed_count: number
  changes: SettlementChange[]
}

export interface LengthPlanView {
  total_target_words: number | null
  actual_total_words: number
  stages: ProjectDataEntry[]
  chapters: Array<Record<string, unknown> & { chapter_number: number; actual_words: number; ref?: string | null }>
}

export interface ProjectData {
  project_id: string
  name: string
  state_rev: number | null
  model_rev: number
  last_authority_source: string | null
  work_direction: string
  reader_promise: string
  settlement: SettlementSummary
  length_plan: LengthPlanView
  sections: ProjectDataSections
}

/** 只读正式 Story State 投影（ProjectData / StoryMap 共用）。 */
export async function getProjectData(projectId: string): Promise<ProjectData> {
  return call<ProjectData>('get_project_data', { project_id: projectId })
}

export interface AuthorEditResult {
  model?: { model_rev: number }
  change: SettlementChange
}

export async function createFoundationRecord(payload: {
  project_id: string
  base_model_rev: number
  category: string
  title: string
  material_state: 'current' | 'future'
  data: Record<string, unknown>
  category_name?: string
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('create_foundation_record', payload)
}

export async function updateFoundationRecord(payload: {
  project_id: string
  base_model_rev: number
  ref: string
  title?: string
  material_state?: 'current' | 'future'
  data?: Record<string, unknown>
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('update_foundation_record', payload)
}

export async function retireFoundationRecord(payload: {
  project_id: string
  base_model_rev: number
  ref: string
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('retire_foundation_record', payload)
}

export async function createRelationship(payload: {
  project_id: string
  base_model_rev: number
  source_ref: string
  target_ref: string
  label: string
  material_state: 'current' | 'future'
  data: Record<string, unknown>
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('create_relationship', payload)
}

export async function updateRelationship(payload: {
  project_id: string
  base_model_rev: number
  ref: string
  source_ref?: string
  target_ref?: string
  label?: string
  material_state?: 'current' | 'future'
  data?: Record<string, unknown>
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('update_relationship', payload)
}

export async function retireRelationship(payload: {
  project_id: string
  base_model_rev: number
  ref: string
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('retire_relationship', payload)
}

export async function setLengthPlan(payload: {
  project_id: string
  base_model_rev: number
  total_target_words: number | null
  stages?: Array<Record<string, unknown>>
  chapter_targets?: Array<Record<string, unknown>>
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('set_length_plan', payload)
}

export async function createChapter(payload: {
  project_id: string
  chapter_number: number
}): Promise<{ project_id: string; chapter_number: number; change: SettlementChange }> {
  return call('create_chapter', payload)
}

export async function saveFormalProse(payload: {
  project_id: string
  chapter_number: number
  base_content_sha256: string
  content: string
}): Promise<{
  project_id: string
  chapter_number: number
  content_sha256: string
  actual_words: number
  change: SettlementChange
  message: string
}> {
  return call('save_formal_prose', payload)
}

export interface ChangeSettlementRequest {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'canceled'
  message?: string
  error?: string | null
  result?: Record<string, unknown>
}

export async function prepareChangeSettlement(payload: {
  project_id: string
  change_id: string
}): Promise<ChangeSettlementRequest> {
  return call('prepare_change_settlement', payload)
}

export async function getChangeSettlementRequest(requestId: string): Promise<ChangeSettlementRequest> {
  return call('get_change_settlement_request', { request_id: requestId })
}

export async function cancelChangeSettlementRequest(requestId: string): Promise<ChangeSettlementRequest> {
  return call('cancel_change_settlement_request', { request_id: requestId })
}

export async function confirmChangeConsequences(payload: {
  project_id: string
  change_id: string
  accepted_indexes: number[]
}): Promise<Record<string, unknown>> {
  return call('confirm_change_consequences', payload)
}

// ---------------- 作品检查（真实、显式、范围受控的 AI 检查） ----------------

export interface ReviewSurface {
  project_id: string
  name: string
  active_plan_count: number
  open_thread_count: number
  chapters: Array<{ chapter_number: number }>
  latest_chapter_number: number | null
  has_accepted_prose: boolean
  settlement?: SettlementSummary
}

export interface ReviewIssue {
  severity: 'priority' | 'watch'
  title: string
  detail: string
  evidence?: string | null
  suggestion: string
}

export interface ReviewReport {
  review_token: string
  project_id: string
  name: string
  chapter_number: number
  summary: string
  issues: ReviewIssue[]
  strengths: string[]
  knowledge: { retrieved_count: number; selected_count: number }
  execution: Record<string, unknown>
  message: string
}

export interface PrepareReviewResult {
  request_id: string
  project_id: string
  name: string
  chapter_number: number
  status: string
  execution_mode: string
  agent_id: string
  model: string | null
  message: string
}

export interface ReviewRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  result?: ReviewReport | null
  error?: string | null
}

/** 确定性只读检查面（无模型）。 */
export async function getReviewSurface(projectId: string): Promise<ReviewSurface> {
  return call<ReviewSurface>('get_review_surface', { project_id: projectId })
}

/** 作者显式"开始检查"→ 后台发起一次 Agent 检查。 */
export async function prepareReview(payload: { project_id: string; chapter_number?: number }): Promise<PrepareReviewResult> {
  return call<PrepareReviewResult>('prepare_review', payload)
}

/** 轮询检查结果：pending 继续等；completed 时 result 含报告。 */
export async function getReviewRequest(requestId: string): Promise<ReviewRequestStatus> {
  return call<ReviewRequestStatus>('get_review_request', { request_id: requestId })
}

/** 取消/丢弃检查：终止运行中的 Direct adapter（如有）。 */
export async function cancelReviewRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call<{ request_id: string; status: string }>('cancel_review_request', { request_id: requestId })
}

// ---------------- 执行记录（验证式审计；只读，显式清理） ----------------

export interface AuthorOperationFacts {
  request_id: string
  /** 归一化操作名：new_project / story_plan / story_write / review / material_classify / material_distill。 */
  kind: string | null
  project_id: string | null
  execution_mode: 'interactive_bridge' | 'direct' | null
  agent_id: string | null
  /** 仅机械已知时非空；交互模式未经执行验证时恒为 null（不编造模型身份）。 */
  model: string | null
  /** 交互两阶段标记（story_write：pending_selection / pending_prose）。 */
  phase: string | null
  /** pending / running / orphaned。orphaned = Direct 请求存在但 worker 已不存在（进程重启）。 */
  state: string | null
  message: string | null
}

/** App 级协调器 remount/reload 后恢复当前待办作者操作；无待办时返回 null。 */
export async function getActiveAuthorOperation(): Promise<AuthorOperationFacts | null> {
  return call<AuthorOperationFacts | null>('get_active_author_operation', {})
}

/** 尽力把 Qoder 桌面端切到前台（全局任务条"前往 Qoder 执行 /gowrite"）。 */
export async function focusQoder(): Promise<{ focused: boolean }> {
  return call<{ focused: boolean }>('focus_qoder', {})
}

export interface ExecutionAuditSummary {
  request_id: string | null
  operation: string | null
  project_id: string | null
  execution_mode: string | null
  agent_id: string | null
  model: string | null
  status: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  event_count: number
  error: string | null
}

export interface ExecutionAuditEvent {
  seq: number
  /** 全局唯一事件身份（跨进程合并 key）；旧版记录可能缺失。 */
  event_id?: string | null
  at: string
  kind: string
  component: string
  verified: boolean
  details?: Record<string, unknown> | null
}

export interface ExecutionAuditRecord extends ExecutionAuditSummary {
  schema: string
  events: ExecutionAuditEvent[]
}

/** 最近执行记录列表（摘要字段；按时间倒序）。 */
export async function listExecutionAudits(payload?: {
  limit?: number
  operation?: string
  status?: string
  project_id?: string
}): Promise<ExecutionAuditSummary[]> {
  return call<ExecutionAuditSummary[]>('list_execution_audits', payload ?? {})
}

/** 单条执行记录（完整事件时间线）；record 为 null 表示不存在。 */
export async function getExecutionAudit(requestId: string): Promise<{ record: ExecutionAuditRecord | null }> {
  return call<{ record: ExecutionAuditRecord | null }>('get_execution_audit', { request_id: requestId })
}

/** 显式清理：只删除 06_工作区/运行审计。 */
export async function clearExecutionAudits(): Promise<{ cleared_files: number; message: string }> {
  return call<{ cleared_files: number; message: string }>('clear_execution_audits', {})
}
