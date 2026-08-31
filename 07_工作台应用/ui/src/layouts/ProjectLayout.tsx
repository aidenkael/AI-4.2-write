import { useEffect, useState, type ReactNode } from 'react'
import { ArrowLeft, CircleCheck } from 'lucide-react'
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
  { id: 'overview', label: '作品概览' }, { id: 'foundation', label: '作品地基' }, { id: 'planning', label: '故事规划' },
  { id: 'writing', label: '正在写' }, { id: 'map', label: '故事地图' }, { id: 'review', label: '作品检查' },
]

function ProjectStateRefreshControl({ projectId }: { projectId: string }) {
  const [state, setState] = useState<ProjectStateRefresh | null>(null)
  const [error, setError] = useState<string | null>(null)
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
  if (state.status === 'running') return <span className="formal-status">正在整理作品状态…</span>
  if (state.status === 'awaiting_confirmation') return (
    <details className="project-state-refresh" open>
      <summary>{state.awaiting_confirmation_count} 项需要确认</summary>
      <ul>{(state.consequences ?? []).map((item, index) => <li key={index}>{item.title ?? '待确认后果'}：{item.reason ?? '请确认是否采用。'}</li>)}</ul>
      <button className="primary" onClick={() => void confirm(true)}>采用这些后果</button>
      <button onClick={() => void confirm(false)}>忽略这些待确认项</button>
    </details>
  )
  if (state.status === 'failed') return <span className="project-state-refresh">整理失败 · <button onClick={() => void refresh()}>重试</button>{error ?? state.error ?? ''}</span>
  if (state.pending_change_count > 0) return <span className="project-state-refresh">{state.pending_change_count} 项修改待整理 <button onClick={() => void refresh()}>更新作品状态</button></span>
  return <span className="formal-status">作品状态已是最新</span>
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
          <span className="formal-status">
            <CircleCheck size={15} />
            正式作品
          </span>
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
        <span className="formal-status">
          <CircleCheck size={15} />
          正式作品
        </span>
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
