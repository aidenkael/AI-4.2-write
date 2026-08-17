/**
 * AI-write 唯一 Bridge 客户端。
 *
 * 规则：React 组件禁止直接调用 `window.pywebview.api`；
 * 所有 Python 调用必须经过本模块。Python 侧唯一暴露入口：
 * `07_工作台应用/backend/bridge/app_api.py`（AppApi）。
 */

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
  data: T
  error?: string
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
      reject(new Error('pywebview bridge 就绪超时：请通过 desktop/main.py 启动应用'))
    }

    const timer = window.setTimeout(onTimeout, timeoutMs)
    const poll = window.setInterval(onReady, 100)
    w.addEventListener?.('pywebviewready', onReady)
    onReady() // 已注入则立即 resolve
  })
}

async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  const api = await whenBridgeReady()
  const result = (await api[method](...args)) as ApiResult<T>
  if (!result || result.ok !== true) {
    throw new Error(result?.error || `${method} 返回异常`)
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
