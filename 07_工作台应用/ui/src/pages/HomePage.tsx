import { useEffect, useState } from 'react'
import { getAppStatus, type AppStatusData } from '../bridge/client'

type BridgeState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: AppStatusData }
  | { kind: 'error'; message: string }

export default function HomePage() {
  const [state, setState] = useState<BridgeState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    getAppStatus()
      .then((data) => { if (!cancelled) setState({ kind: 'ok', data }) })
      .catch((err) => { if (!cancelled) setState({ kind: 'error', message: String(err) }) })
    return () => { cancelled = true }
  }, [])

  return (
    <p style={{ marginTop: '1.5rem', fontSize: '1.05rem' }}>
      {state.kind === 'loading' && '正在连接工作台…'}
      {state.kind === 'ok' && `${state.data.message}（${state.data.app_name} · ${state.data.status}）`}
      {state.kind === 'error' && `Bridge 错误：${state.message}`}
    </p>
  )
}
