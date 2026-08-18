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

export interface AgentCapabilities {
  run: boolean
  cancel: boolean
  model_selection: string
  byok?: boolean
  reasoning_effort?: boolean
  [key: string]: unknown
}

export interface AgentInfo {
  id: string
  available: boolean
  capabilities: AgentCapabilities | null
  error: string | null
}

export interface ByokModel {
  key: string | null
  display_name: string | null
  is_reasoning?: boolean | null
  efforts?: string[]
}

export interface ByokType {
  key: string | null
  display_name: string | null
  models: ByokModel[]
}

export interface ByokProvider {
  key: string | null
  display_name: string | null
  types: ByokType[]
}

export interface AgentSettings {
  default_agent: string
  qoder_mode: string
  qoder_model: string | null
  reasoning_effort: string | null
  byok_provider: string | null
  byok_model: string | null
  byok_secret_id: string | null
}

export interface AgentSettingsData {
  settings: AgentSettings
  agents: AgentInfo[]
  byok: { secret_id: string | null; has_secret: boolean }
}

export interface AgentOptionsData {
  qoder_models: string[]
  qoder_models_error: string | null
  byok_providers: ByokProvider[]
  byok_error: string | null
  reasoning_effort_options: string[]
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

/** 动态选项：Qoder 自带模型 / BYOK provider-model / 思考强度。 */
export async function getAgentOptions(): Promise<AgentOptionsData> {
  return call<AgentOptionsData>('get_agent_options')
}

/** 保存普通设置（不含 Token）。 */
export async function saveAgentSettings(settings: {
  default_agent: string
  qoder_mode?: string
  qoder_model?: string | null
  reasoning_effort?: string | null
  byok_provider?: string | null
  byok_model?: string | null
}): Promise<{ settings: AgentSettings }> {
  return call<{ settings: AgentSettings }>('save_agent_settings', settings)
}

/** 保存 BYOK Token 到 keyring（只返回 secret_id + has_secret，绝不明文）。 */
export async function saveByokSecret(token: string): Promise<{ secret_id: string; has_secret: boolean }> {
  return call<{ secret_id: string; has_secret: boolean }>('save_byok_secret', token)
}

/** 删除 BYOK Token；删除后状态立即变为未配置。 */
export async function deleteByokSecret(): Promise<{ secret_id: string | null; has_secret: boolean }> {
  return call<{ secret_id: string | null; has_secret: boolean }>('delete_byok_secret')
}

/** 测试连接（无副作用任务 + 临时目录）；BYOK 未配置 Token 时返回 not_configured。 */
export async function testAgentConnection(payload: {
  agent: string
  qoder_mode?: string
  qoder_model?: string | null
  reasoning_effort?: string | null
  byok_provider?: string | null
  byok_model?: string | null
}): Promise<ConnectionTestResult> {
  return call<ConnectionTestResult>('test_agent_connection', payload)
}

// ---------------- 新建作品（“我有个想法”纵切） ----------------

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

export interface ConfirmResult {
  project_id: string
  name: string
  project_dir: string
  state_rev: number | null
  approved_direction_registered: boolean
  warning: string | null
  message: string
}

/** 我有个想法 → 当前 Agent 设置 → StoryDesign 候选（不写正式作品）。 */
export async function proposeNewProject(payload: { name: string; idea: string }): Promise<ProposeResult> {
  return call<ProposeResult>('propose_new_project', payload)
}

/** 作者明确确认 → 用后台保存的候选创建正式作品。 */
export async function confirmNewProject(payload: { proposal_token: string }): Promise<ConfirmResult> {
  return call<ConfirmResult>('confirm_new_project', payload)
}
