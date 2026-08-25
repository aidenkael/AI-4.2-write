import type { ReactNode } from 'react'
import { ArrowLeft, CircleCheck } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import type { ProjectSection } from '../contracts/ui'

// 全部作品内页面已接入正式项目外壳，使用同一正式 project_id，禁止 Mock 身份。
const items: Array<{ id: ProjectSection; label: string }> = [
  { id: 'development', label: '故事发展' }, { id: 'writing', label: '正在写' }, { id: 'map', label: '故事地图' },
  { id: 'data', label: '作品资料' }, { id: 'review', label: '作品检查' },
]

export function ProjectLayout({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const { selected } = useFormalProjectShell()

  // 没有正式项目选择：绝不用 Mock 项目顶替，显示安全空态并引导回作品列表
  if (!selected) {
    return (
      <div className="project-shell">
        <header className="projectbar">
          <button className="project-title" onClick={() => actions.navigate('projects')}>
            <ArrowLeft />
            作品列表
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
        <button className="project-title" onClick={() => actions.navigate('projects')}>
          <ArrowLeft />
          {selected.name}
        </button>
        <span className="formal-status">
          <CircleCheck size={15} />
          正式作品
        </span>
        <nav aria-label="作品内导航">
          <button
            className={state.projectSection === 'overview' ? 'active' : ''}
            onClick={() => actions.setProjectSection('overview')}
          >
            作品概览
          </button>
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
      <div className="project-content">{children}</div>
    </div>
  )
}
