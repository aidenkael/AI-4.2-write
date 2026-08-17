import { useEffect, useState } from 'react'
import { getAppStatus, type AppStatusData } from './bridge/client'

const NAV_ITEMS = ['首页', '我的作品', '素材与学习', '灵感箱', '搜索', '设置']

type BridgeState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: AppStatusData }
  | { kind: 'error'; message: string }

export default function App() {
  const [state, setState] = useState<BridgeState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    getAppStatus()
      .then((data) => { if (!cancelled) setState({ kind: 'ok', data }) })
      .catch((err) => { if (!cancelled) setState({ kind: 'error', message: String(err) }) })
    return () => { cancelled = true }
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, "Microsoft YaHei", sans-serif', padding: '1rem 1.5rem' }}>
      <h1>AI-write</h1>
      <nav style={{ display: 'flex', gap: '1.25rem', margin: '0.5rem 0 1rem' }}>
        {NAV_ITEMS.map((item) => <span key={item}>{item}</span>)}
      </nav>
      <hr />
      {/* 骨架验证区：显示的文字必须来自 Python Bridge 返回的数据（state.data.message），不在 React 写死 */}
      <p style={{ marginTop: '1.5rem', fontSize: '1.05rem' }}>
        {state.kind === 'loading' && '正在连接工作台…'}
        {state.kind === 'ok' && `${state.data.message}（${state.data.app_name} · ${state.data.status}）`}
        {state.kind === 'error' && `Bridge 错误：${state.message}`}
      </p>
    </div>
  )
}
