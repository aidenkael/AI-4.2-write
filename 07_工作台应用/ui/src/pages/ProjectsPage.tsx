import { useEffect, useState } from 'react'
import { listProjects, type ProjectItem } from '../bridge/client'

type State =
  | { kind: 'loading' }
  | { kind: 'ok'; projects: ProjectItem[] }
  | { kind: 'error'; message: string }

export default function ProjectsPage({ onOpen }: { onOpen: (p: ProjectItem) => void }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    listProjects()
      .then((projects) => { if (!cancelled) setState({ kind: 'ok', projects }) })
      .catch((err) => { if (!cancelled) setState({ kind: 'error', message: String(err) }) })
    return () => { cancelled = true }
  }, [])

  return (
    <section>
      <h2>我的作品</h2>
      {state.kind === 'loading' && <p>正在读取作品列表…</p>}
      {state.kind === 'error' && <p>读取失败：{state.message}</p>}
      {state.kind === 'ok' && (
        state.projects.length === 0 ? (
          <p>暂无作品</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {state.projects.map((p) => (
              <li key={p.project_id} style={{ margin: '0.5rem 0' }}>
                <button onClick={() => onOpen(p)} style={{ cursor: 'pointer' }}>{p.name}</button>
                <span style={{ marginLeft: '0.75rem', color: '#888', fontSize: '0.85rem' }}>{p.project_id}</span>
              </li>
            ))}
          </ul>
        )
      )}
    </section>
  )
}
