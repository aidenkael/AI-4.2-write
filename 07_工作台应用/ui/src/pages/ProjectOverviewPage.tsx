import { useEffect, useState } from 'react'
import { getProjectOverview, type ProjectOverview } from '../bridge/client'

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; overview: ProjectOverview }
  | { kind: 'error'; message: string }

export default function ProjectOverviewPage({
  projectId,
  projectName,
  onBack,
}: {
  projectId: string
  projectName: string
  onBack: () => void
}) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    getProjectOverview(projectId)
      .then((overview) => { if (!cancelled) setState({ kind: 'ok', overview }) })
      .catch((err) => { if (!cancelled) setState({ kind: 'error', message: String(err) }) })
    return () => { cancelled = true }
  }, [projectId])

  return (
    <section>
      <h2>作品概览：{projectName}</h2>
      <button onClick={onBack} style={{ cursor: 'pointer' }}>← 返回作品列表</button>
      {state.kind === 'loading' && <p>正在读取概览…</p>}
      {state.kind === 'error' && <p>读取失败：{state.message}</p>}
      {state.kind === 'ok' && (
        <div style={{ marginTop: '0.75rem', lineHeight: 1.7 }}>
          <p>
            <strong>{state.overview.name}</strong>
            <span style={{ marginLeft: '0.75rem', color: '#888', fontSize: '0.85rem' }}>
              {state.overview.project_id}
            </span>
          </p>
          <p>
            基础状态：state_rev {state.overview.state.state_rev} ·
            最近权威来源 {state.overview.state.last_authority_source}
          </p>
          {state.overview.last_accepted && (
            <p>
              最近写作位置：{state.overview.last_accepted.chapter_path}
              （scene_ref: {state.overview.last_accepted.scene_ref}）
            </p>
          )}
          {state.overview.recent_prose && (
            <p>
              最近正文窗口：{state.overview.recent_prose.window_chars} 字
              （scene_ref: {state.overview.recent_prose.scene_ref}）
            </p>
          )}
          {state.overview.planning && (
            <p>
              当前规划：{state.overview.planning.entries} 条
              {state.overview.planning.latest ? ` · 最新：${state.overview.planning.latest}` : ''}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
