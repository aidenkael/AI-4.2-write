import { useEffect, useState, type ReactNode } from 'react'
import { ArrowLeft, X } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import type { ProjectSection } from '../contracts/ui'
import { ProjectPageErrorBoundary } from '../components/ProjectPageErrorBoundary'
import {
  confirmProjectStateRefresh,
  getProjectStateRefresh,
  prepareProjectStateRefresh,
  type ProjectStateRefresh,
} from '../bridge/client'

// Go Write 2.0 作品内六任务；全部作品内页面已接入正式项目外壳，使用同一正式 project_id，禁止 Mock 身份。
const items: Array<{ id: ProjectSection; label: string }> = [
  { id: 'overview', label: '作品概览' }, { id: 'foundation', label: '作品地基' }, { id: 'planning', label: '大纲与规划' },
  { id: 'writing', label: '正文管理' }, { id: 'map', label: '故事地图' }, { id: 'review', label: '作品检查' },
]

function ProjectStateRefreshControl({ projectId }: { projectId: string }) {
  const [state, setState] = useState<ProjectStateRefresh | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmationOpen, setConfirmationOpen] = useState(false)
  const load = async () => {
    try {
      setState(await getProjectStateRefresh(projectId))
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }
  useEffect(() => {
    void load()
    const refreshOnMutation = () => { void load() }
    const eventTarget = window
    eventTarget.addEventListener('gowrite-project-mutated', refreshOnMutation)
    return () => eventTarget.removeEventListener('gowrite-project-mutated', refreshOnMutation)
  }, [projectId])
  useEffect(() => {
    if (state?.status !== 'running') return
    const timer = window.setInterval(() => { void load() }, 1500)
    return () => window.clearInterval(timer)
  }, [state?.status, projectId])
  if (!state) return null
  const refresh = async () => {
    try { setState(await prepareProjectStateRefresh({ project_id: projectId })) } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }
  const confirm = async (accept: boolean) => {
    if (!state.refresh_id) return
    try {
      setState(await confirmProjectStateRefresh({ project_id: projectId, refresh_id: state.refresh_id, accept }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }
  if (state.status === 'running') return <span className="project-state-refresh compact">正在整理作品状态…</span>
  if (state.status === 'awaiting_confirmation') return (
    <>
      <button className="project-state-refresh compact" onClick={() => setConfirmationOpen(true)}>
        {state.awaiting_confirmation_count} 项需要确认
      </button>
      {confirmationOpen && (
        <aside className="record-drawer project-state-refresh-drawer panel" aria-label="确认作品状态后果">
          <header><h2>{state.awaiting_confirmation_count} 项需要确认</h2><button aria-label="关闭" onClick={() => setConfirmationOpen(false)}><X /></button></header>
          <div className="record-drawer-body">
            <p className="muted-note">这些是根据已保存修改整理出的后果；采用前不会写入作品。</p>
            <ul className="project-state-consequences">{(state.consequences ?? []).map((item, index) => <li key={index}><strong>{item.title ?? '待确认后果'}</strong><span>{item.reason ?? '请确认是否采用。'}</span></li>)}</ul>
          </div>
          <footer><button onClick={() => void confirm(false)}>忽略这些待确认项</button><button className="primary" onClick={() => void confirm(true)}>采用这些后果</button></footer>
        </aside>
      )}
    </>
  )
  if (state.status === 'failed') return <button className="project-state-refresh compact failed" title={error ?? state.error ?? '整理失败，请重试。'} onClick={() => void refresh()}>整理失败 · 重试</button>
  if (state.pending_change_count > 0) return <button className="project-state-refresh compact" onClick={() => void refresh()}>{state.pending_change_count} 项修改待整理 · 更新作品状态</button>
  return null
}

export function ProjectLayout({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const { selected } = useFormalProjectShell()

  // 没有正式项目选择：绝不用 Mock 项目顶替，显示安全空态并引导回作品页
  if (!selected) {
    return (
      <div className="project-shell">
        <header className="projectbar">
          <button className="project-title" onClick={() => actions.navigate('works')}>
            <ArrowLeft />
            作品
          </button>
        </header>
        <div className="project-content">
          <div className="empty-state">请先选择一部正式作品，再进入作品内页面。</div>
        </div>
      </div>
    )
  }

  return (
    <div className="project-shell">
      <header className="projectbar">
        <button className="project-title" onClick={() => actions.navigate('works')}>
          <ArrowLeft />
          {selected.name}
        </button>
        <ProjectStateRefreshControl projectId={selected.project_id} />
        <nav aria-label="作品内导航">
          {items.map((item) => (
            <button
              key={item.id}
              className={state.projectSection === item.id ? 'active' : ''}
              onClick={() => actions.setProjectSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>
      <div className="project-content"><ProjectPageErrorBoundary pageKey={state.projectSection ?? 'none'}>{children}</ProjectPageErrorBoundary></div>
    </div>
  )
}
