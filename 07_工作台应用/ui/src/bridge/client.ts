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
  intent_rev?: number
  story_synopsis?: string
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
  open_items?: {
    total: number
    items: Array<{ id?: string | null; title: string; kind: string; status: string }>
  }
  /** 规划影响紧凑状态：只给计数，明细在大纲与规划页处理。 */
  planning_impact?: {
    pending_count: number
    deferred_count: number
  }
  primary_next_action?: 'foundation' | 'writing'
  settlement?: SettlementSummary
}

interface ApiResult<T> {
  ok: boolean
  data: T | null
  error: { code: string; message: string } | null
}

const projectMutationMethods = new Set([
  'create_foundation_record', 'update_foundation_record', 'retire_foundation_record', 'restore_foundation_record',
  'create_relationship', 'update_relationship', 'retire_relationship', 'restore_relationship',
  'set_length_plan', 'set_story_bible_profile', 'save_formal_prose', 'confirm_story_write',
  'confirm_story_plan', 'confirm_foundation_design', 'confirm_project_state_refresh',
  'update_story_synopsis', 'set_planning_impact_candidate_status',
])

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
  if (projectMutationMethods.has(method)) window.dispatchEvent?.(new Event('gowrite-project-mutated'))
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

export async function updateStorySynopsis(payload: {
  project_id: string
  base_intent_rev: number
  story_synopsis: string
}): Promise<{ project_id: string; intent_rev: number; story_synopsis: string; change: SettlementChange }> {
  return call('update_story_synopsis', payload)
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

// ---------------- 日常 AI（Direct AI 语义结算；独立于 Agent 执行设置） ----------------

export interface SemanticAiSettings {
  semantic_ai_base_url: string
  semantic_ai_model: string
  /** API Key 只存在于系统凭据存储；前端永远只能看到是否已配置。 */
  has_api_key: boolean
  configured: boolean
}

export async function getSemanticAiSettings(): Promise<SemanticAiSettings> {
  return call<SemanticAiSettings>('get_semantic_ai_settings')
}

/** 保存日常 AI 设置；提供 api_key 时只写入 OS keyring，绝不回传明文。 */
export async function saveSemanticAiSettings(payload: {
  semantic_ai_base_url: string
  semantic_ai_model: string
  api_key?: string
}): Promise<{ settings: SemanticAiSettings }> {
  return call<{ settings: SemanticAiSettings }>('save_semantic_ai_settings', payload)
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
  /** 显式领域关系投影（future；端点只用 key 或同项目 ref，不按标题猜）。 */
  domain_relations?: Array<Record<string, unknown>>
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

/** 一起往前想 → 按已保存 Settings 准备本轮任务（Interactive 等待 /gowrite；Direct 后台执行），返回 request_id。
 *
 * 结构化模式（可选）：planning_mode 与附带范围；impact_replan 必须携带精确的
 * 影响候选 id，后端拒绝未知候选。
 */
export async function prepareStoryPlan(payload: {
  project_id: string
  author_question: string
  planning_mode?: string
  impact_candidate_ids?: string[]
  replaces_plan_ids?: string[]
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

export interface PlanningImpactStatusResult {
  model_rev: number
  planning_impact_candidates: Array<Record<string, unknown>>
}

/** 作者显式处置影响候选：暂时保留（deferred）/ 恢复待处理（pending_author）。
 * 绝不自动重规划；重规划只走 prepareStoryPlan 的 impact_replan 显式路径。 */
export async function setPlanningImpactCandidateStatus(payload: {
  project_id: string
  candidate_id: string
  status: 'deferred' | 'pending_author'
}): Promise<PlanningImpactStatusResult> {
  return call<PlanningImpactStatusResult>('set_planning_impact_candidate_status', payload)
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
  formal_prose_exists: boolean
  stage_ref?: string | null
  stage_title?: string | null
  content_sha256?: string
  accepted?: boolean
  fine_outline_ref?: string | null
  fine_outline?: Record<string, unknown>
  actual_result?: Record<string, unknown> | null
  previous_actual_result?: Record<string, unknown> | null
}

export interface StoryWriteSurface {
  project_id: string
  name: string
  chapters: StoryWriteChapter[]
  active_chapter_number: number
  total_words: number
  settlement?: SettlementSummary
  state_refresh?: ProjectStateRefresh
  open_threads?: Array<{ title: string; status: 'current' | 'future' }>
  planning_impact_candidates?: Array<Record<string, unknown>>
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
  locations: ProjectDataEntry[]
  organizations: ProjectDataEntry[]
  systems: ProjectDataEntry[]
  occurred_events: ProjectDataEntry[]
  open_threads: ProjectDataEntry[]
  foreshadowing: ProjectDataEntry[]
  storylines: ProjectDataEntry[]
  mystery_information: ProjectDataEntry[]
  approved_plan: ProjectDataEntry[]
}

/** 同一 ProjectModel 的活动显式关系事实（只读派生；普通可见 UI 只渲染标题不渲染 ref）。 */
export interface ExplicitDependency {
  ref: string
  relation_kind: string
  title: string
  material_state: 'current' | 'future'
  source_ref: string
  source_title: string
  source_category: string | null
  target_ref: string
  target_title: string
  target_category: string | null
  data?: Record<string, unknown>
}

/** 作者提交的关系选择条目（完整受管集合；source 由被编辑记录自身确定）。 */
export interface RelationSelection {
  relation_kind: string
  target_ref: string
  data?: Record<string, unknown>
}

export interface StoryBibleProfile {
  genre_tags: string[]
  narrative_mode: string | null
  active_modules: string[]
  field_config: Record<string, unknown>
}

export interface SettlementChange {
  change_id: string
  source_kind: string
  status: 'pending' | 'failed' | 'awaiting_author' | 'synchronized' | 'canceled'
  delta: Record<string, unknown>
  semantic?: { summary?: string; consequences?: Array<Record<string, unknown>> } | null
  error?: string | null
  requires_semantic?: boolean
  settlement_request_id?: string | null
  settlement_started?: boolean
}

export interface ProjectStateRefresh {
  status: 'synchronized' | 'running' | 'awaiting_confirmation' | 'failed'
  pending_change_count: number
  awaiting_confirmation_count: number
  refresh_id: string | null
  worker_active: boolean
  summary: string | null
  error: string | null
  cutoff_sequence?: number
  consequences?: Array<{ title?: string; reason?: string; classification?: string }>
}

export interface SettlementSummary {
  status: 'synchronized' | 'pending' | 'failed'
  pending_count: number
  failed_count: number
  /** 存在“需要配置日常 AI”的可恢复失败；配置后可重试，不是故事数据错误。 */
  needs_semantic_ai_config?: boolean
  /** 本进程结算 worker 是否真实在跑；陈旧 request_id 绝不得呈现为正在同步。 */
  worker_active?: boolean
  changes: SettlementChange[]
}

export interface LengthPlanView {
  total_target_words: number | null
  actual_total_words: number
  stages: ProjectDataEntry[]
  chapters: Array<Record<string, unknown> & { chapter_number: number; actual_words: number; formal_prose_exists?: boolean; ref?: string | null }>
}

export interface ProjectData {
  project_id: string
  name: string
  state_rev: number | null
  model_rev: number
  last_authority_source: string | null
  work_direction: string
  reader_promise: string
  story_synopsis?: string
  settlement: SettlementSummary
  state_refresh: ProjectStateRefresh
  story_bible_profile: StoryBibleProfile
  length_plan: LengthPlanView
  chapters: Array<{
    chapter_number: number
    title: string
    actual_words: number
    formal_prose_exists: boolean
    fine_outline: Record<string, unknown>
    actual_result: Record<string, unknown> | null
  }>
  planning_impact_candidates: Array<Record<string, unknown>>
  /** 活动显式关系事实（人物关系 + 批准的领域关系；派生只读）。 */
  explicit_dependencies: ExplicitDependency[]
  /** 已退役源记录：可见可恢复，但绝不混入 current/future，也不进入故事地图活动视图。 */
  retired: { foundation: ProjectDataEntry[]; relationships: ProjectDataEntry[] }
  sections: ProjectDataSections
}

const PROJECT_DATA_SECTION_KEYS: Array<keyof ProjectDataSections> = [
  'characters', 'relationships', 'canon_facts', 'locations', 'organizations', 'systems',
  'occurred_events', 'open_threads', 'foreshadowing', 'storylines', 'mystery_information', 'approved_plan',
]

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
)

function projectDataInvalid(reason: string): never {
  throw new BridgeError('PROJECT_DATA_INVALID', `作品数据结构不完整，已拒绝加载：${reason}`)
}

function requireRecord(value: unknown, name: string): Record<string, unknown> {
  if (!isRecord(value)) projectDataInvalid(`${name} 必须是对象`)
  return value
}

function requireArray(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) projectDataInvalid(`${name} 必须是数组`)
  return value
}

function requireNumber(value: unknown, name: string, nullable = false): void {
  if ((nullable && value === null) || typeof value === 'number') return
  projectDataInvalid(`${name} 必须是${nullable ? '数字或 null' : '数字'}`)
}

function requireProjectEntries(value: unknown, name: string): void {
  for (const [index, entry] of requireArray(value, name).entries()) {
    const record = requireRecord(entry, `${name}[${index}]`)
    if (!(record.id === null || typeof record.id === 'string') || typeof record.label !== 'string') {
      projectDataInvalid(`${name}[${index}] 缺少稳定条目身份`)
    }
  }
}

/** ProjectData 是跨版本 UI 的共享边界：后端必须完整投影，客户端只验证/拒绝。 */
export function validateProjectData(value: unknown): ProjectData {
  const data = requireRecord(value, 'ProjectData')
  if (typeof data.project_id !== 'string' || !data.project_id || typeof data.name !== 'string') {
    projectDataInvalid('缺少正式作品身份')
  }
  requireNumber(data.model_rev, 'model_rev')
  requireNumber(data.state_rev, 'state_rev', true)
  if (typeof data.work_direction !== 'string' || typeof data.reader_promise !== 'string') {
    projectDataInvalid('作品方向字段非法')
  }

  const settlement = requireRecord(data.settlement, 'settlement')
  if (!['synchronized', 'pending', 'failed'].includes(String(settlement.status))) projectDataInvalid('settlement.status 非法')
  requireNumber(settlement.pending_count, 'settlement.pending_count')
  requireNumber(settlement.failed_count, 'settlement.failed_count')
  requireArray(settlement.changes, 'settlement.changes')
  const refresh = requireRecord(data.state_refresh, 'state_refresh')
  if (!['synchronized', 'running', 'awaiting_confirmation', 'failed'].includes(String(refresh.status))) {
    projectDataInvalid('state_refresh.status 非法')
  }
  requireNumber(refresh.pending_change_count, 'state_refresh.pending_change_count')
  requireNumber(refresh.awaiting_confirmation_count, 'state_refresh.awaiting_confirmation_count')

  const profile = requireRecord(data.story_bible_profile, 'story_bible_profile')
  if (!Array.isArray(profile.genre_tags) || profile.genre_tags.some((tag) => typeof tag !== 'string')
    || !(profile.narrative_mode === null || typeof profile.narrative_mode === 'string')
    || !Array.isArray(profile.active_modules) || profile.active_modules.some((module) => typeof module !== 'string')
    || !isRecord(profile.field_config)) projectDataInvalid('story_bible_profile 字段非法')

  const lengthPlan = requireRecord(data.length_plan, 'length_plan')
  requireNumber(lengthPlan.total_target_words, 'length_plan.total_target_words', true)
  requireNumber(lengthPlan.actual_total_words, 'length_plan.actual_total_words')
  requireProjectEntries(lengthPlan.stages, 'length_plan.stages')
  for (const [index, chapter] of requireArray(lengthPlan.chapters, 'length_plan.chapters').entries()) {
    const record = requireRecord(chapter, `length_plan.chapters[${index}]`)
    requireNumber(record.chapter_number, `length_plan.chapters[${index}].chapter_number`)
    requireNumber(record.actual_words, `length_plan.chapters[${index}].actual_words`)
    if (record.formal_prose_exists !== undefined && typeof record.formal_prose_exists !== 'boolean') {
      projectDataInvalid(`length_plan.chapters[${index}].formal_prose_exists 必须是布尔值`)
    }
  }
  for (const [index, chapter] of requireArray(data.chapters, 'chapters').entries()) {
    const record = requireRecord(chapter, `chapters[${index}]`)
    requireNumber(record.chapter_number, `chapters[${index}].chapter_number`)
    requireNumber(record.actual_words, `chapters[${index}].actual_words`)
    if (typeof record.formal_prose_exists !== 'boolean') {
      projectDataInvalid(`chapters[${index}].formal_prose_exists 必须是布尔值`)
    }
  }
  requireArray(data.planning_impact_candidates, 'planning_impact_candidates')
  for (const [index, edge] of requireArray(data.explicit_dependencies, 'explicit_dependencies').entries()) {
    const record = requireRecord(edge, `explicit_dependencies[${index}]`)
    for (const key of ['ref', 'relation_kind', 'source_ref', 'target_ref'] as const) {
      if (typeof record[key] !== 'string' || !(record[key] as string)) {
        projectDataInvalid(`explicit_dependencies[${index}].${key} 非法`)
      }
    }
    if (record.material_state !== 'current' && record.material_state !== 'future') {
      projectDataInvalid(`explicit_dependencies[${index}].material_state 非法`)
    }
  }
  const sections = requireRecord(data.sections, 'sections')
  for (const key of PROJECT_DATA_SECTION_KEYS) requireProjectEntries(sections[key], `sections.${key}`)
  const retired = requireRecord(data.retired, 'retired')
  requireProjectEntries(retired.foundation, 'retired.foundation')
  requireProjectEntries(retired.relationships, 'retired.relationships')
  return data as unknown as ProjectData
}

/** 统一只读项目快照投影（ProjectData / StoryMap 共用，不是第二 truth store）。 */
export async function getProjectData(projectId: string): Promise<ProjectData> {
  return validateProjectData(await call<unknown>('get_project_data', { project_id: projectId }))
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
  relations?: RelationSelection[]
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('create_foundation_record', payload)
}

export async function setStoryBibleProfile(payload: {
  project_id: string
  base_model_rev: number
  genre_tags: string[]
  narrative_mode: string | null
  active_modules: string[]
  field_config: Record<string, unknown>
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('set_story_bible_profile', payload)
}

export async function updateFoundationRecord(payload: {
  project_id: string
  base_model_rev: number
  ref: string
  title?: string
  material_state?: 'current' | 'future'
  data?: Record<string, unknown>
  relations?: RelationSelection[]
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

export async function restoreFoundationRecord(payload: {
  project_id: string
  base_model_rev: number
  ref: string
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('restore_foundation_record', payload)
}

export async function restoreRelationship(payload: {
  project_id: string
  base_model_rev: number
  ref: string
}): Promise<AuthorEditResult> {
  return call<AuthorEditResult>('restore_relationship', payload)
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

export async function prepareProjectStateRefresh(payload: { project_id: string }): Promise<ProjectStateRefresh> {
  return call('prepare_project_state_refresh', payload)
}

export async function getProjectStateRefresh(projectId: string): Promise<ProjectStateRefresh> {
  return call('get_project_state_refresh', { project_id: projectId })
}

export async function confirmProjectStateRefresh(payload: {
  project_id: string
  refresh_id: string
  accept: boolean
}): Promise<ProjectStateRefresh> {
  return call('confirm_project_state_refresh', payload)
}

// ---------------- M3 知识驱动重大基座设计（Agent 主导；候选 ≠ authority） ----------------

export interface FoundationDesignItem {
  kind: 'character' | 'relationship' | 'world_setting' | 'location' | 'organization' | 'system' | 'story_line' | 'promise_foreshadowing' | 'mystery_information' | 'core_conflict'
  candidate_key?: string | null
  title: string
  summary?: string
  data?: Record<string, unknown>
  material_state: 'current' | 'future'
  source_key?: string | null
  target_key?: string | null
  source_ref?: string | null
  target_ref?: string | null
  source_title?: string
  target_title?: string
  label?: string
}

export interface FoundationDesignDomainRelation {
  relation_kind: string
  source_key?: string | null
  target_key?: string | null
  source_ref?: string | null
  target_ref?: string | null
}

export interface FoundationDesignCandidate {
  status: string
  objective: string
  topics: string[]
  rounds: Array<{ topic: string; query: string; comparison: string; selected_count: number }>
  proposal: {
    characters: FoundationDesignItem[]
    relationships: FoundationDesignItem[]
    world_settings: FoundationDesignItem[]
    locations: FoundationDesignItem[]
    organizations: FoundationDesignItem[]
    systems: FoundationDesignItem[]
    story_lines: FoundationDesignItem[]
    promise_foreshadowing: FoundationDesignItem[]
    mystery_information: FoundationDesignItem[]
    core_conflict: FoundationDesignItem | null
    domain_relations?: FoundationDesignDomainRelation[]
  }
  assumptions: string[]
  knowledge_notes: string
  knowledge: { rounds: number; selected_count: number; source_kinds: string[] }
}

export interface FoundationDesignResult {
  proposal_token: string
  project_id: string
  status: string
  candidate: FoundationDesignCandidate
  execution?: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
  message: string
}

export async function prepareFoundationDesign(payload: {
  project_id: string
  author_request: string
  base_model_rev: number
}): Promise<{ request_id: string; project_id: string; status: string; execution_mode?: string | null; agent_id?: string | null; model?: string | null; message?: string }> {
  return call('prepare_foundation_design', payload)
}

export async function getFoundationDesignRequest(requestId: string): Promise<{
  request_id: string
  status: string
  phase?: string | null
  message?: string | null
  error?: string | null
  result?: FoundationDesignResult | null
}> {
  return call('get_foundation_design_request', { request_id: requestId })
}

export async function cancelFoundationDesignRequest(requestId: string): Promise<{ request_id: string; status: string }> {
  return call('cancel_foundation_design_request', { request_id: requestId })
}

export async function confirmFoundationDesign(payload: {
  project_id: string
  proposal_token: string
  items: FoundationDesignItem[]
  /** 作者选中采用的显式领域关系（只发送选中的；未选不写）。 */
  relations?: FoundationDesignDomainRelation[]
  base_model_rev: number
}): Promise<{ project_id: string; model_rev: number; created: Array<{ kind: string; title: string; ref: string }>; warnings: string[]; settlement_started: boolean; message: string }> {
  return call('confirm_foundation_design', payload)
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
