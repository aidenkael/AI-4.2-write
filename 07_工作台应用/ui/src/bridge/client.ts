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
}

export interface InteractiveEnvironment {
  available: boolean
  bridge_ready: boolean
  command_name: string
  command_ready: boolean
  relevant_status?: Record<string, string | null>
  repair_hint?: string | null
}

export interface DirectEnvironment {
  available: boolean
  auth_status: string
  model_selection: 'selectable' | 'managed' | 'none'
  models: DiscoveredModel[]
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
}

export interface AgentSettingsData {
  settings: AgentSettings
  agents: AgentEnvironment[]
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

/** 保存普通设置（不含 Token）。 */
export async function saveAgentSettings(settings: Partial<AgentSettings>): Promise<{ settings: AgentSettings }> {
  return call<{ settings: AgentSettings }>('save_agent_settings', settings)
}

/** 在官方 Qoder CN 命令位置安装/修复唯一 Go Write 命令定义。 */
export async function installOrRepairInteractiveCommand(agent: string): Promise<{ installed_paths: string[]; command_ready: boolean; errors: string[] }> {
  return call('install_or_repair_interactive_command', { agent })
}

/** 测试连接（无副作用任务 + 临时目录）；BYOK 未配置 Token 时返回 not_configured。 */
export async function testAgentConnection(payload: {
  agent: string
  model?: string | null
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
  message: string
}

export interface PrepareNewProjectResult {
  request_id: string
  name: string
  status: string
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
// 统一 /gowrite 桥模式：Go Write 准备任务 → Qoder /gowrite → 结果返回

export interface StoryPlanCandidate {
  proposal: string
  planning_items: string[]
}

export interface ProposeStoryPlanResult {
  planning_token: string
  project_id: string
  name: string
  status: string
  candidate: StoryPlanCandidate
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
  message: string
}

export interface StoryPlanRequestStatus {
  request_id: string
  status: 'pending' | 'completed' | 'failed' | 'expired' | 'canceled'
  result?: ProposeStoryPlanResult | null
  error?: string | null
}

/** 一起往前想 → Go Write 准备本轮 Agent 任务（不运行模型），返回 request_id。 */
export async function prepareStoryPlan(payload: {
  project_id: string
  author_question: string
}): Promise<PrepareStoryPlanResult> {
  return call<PrepareStoryPlanResult>('prepare_story_plan', payload)
}

/** 轮询 Qoder 写回结果：pending 继续等；completed 时 result 含候选。 */
export async function getStoryPlanRequest(requestId: string): Promise<StoryPlanRequestStatus> {
  return call<StoryPlanRequestStatus>('get_story_plan_request', { request_id: requestId })
}

/** 取消等待：旧结果不可能再被接受。 */
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

export interface ProposeStoryWriteResult {
  writing_token: string
  project_id: string
  name: string
  scene_ref: string
  chapter_number: number
  draft_text: string
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

/** 正文写作：当前暂不可用（正在接入统一 Qoder 执行方式）。 */
export async function proposeStoryWrite(payload: {
  project_id: string
  author_input: string
}): Promise<ProposeStoryWriteResult> {
  return call<ProposeStoryWriteResult>('propose_story_write', payload)
}

/** 作者明确"保留这段" → accept_prose 写入正式 03_正文。 */
export async function confirmStoryWrite(payload: {
  project_id: string
  writing_token: string
}): Promise<ConfirmStoryWriteResult> {
  return call<ConfirmStoryWriteResult>('confirm_story_write', payload)
}
