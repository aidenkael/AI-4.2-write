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

interface ApiResult<T> {
  ok: boolean
  data: T
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

/** 获取应用状态（骨架验证用；数据来自 Python AppApi.get_app_status）。 */
export async function getAppStatus(): Promise<AppStatusData> {
  const api = await whenBridgeReady()
  const result = (await api.get_app_status()) as ApiResult<AppStatusData>
  if (!result || result.ok !== true) {
    throw new Error('get_app_status 返回异常')
  }
  return result.data
}
