import type { ReactNode } from 'react'
import { ArrowLeft, CircleCheck } from 'lucide-react'
import { useActiveProject, useApp, useIllustration } from '../features/app/AppStore'
import type { ProjectSection } from '../contracts/ui'

const items: Array<{ id: ProjectSection; label: string }> = [
  { id: 'development', label: '故事发展' }, { id: 'writing', label: '正在写' }, { id: 'map', label: '故事地图' },
  { id: 'data', label: '作品资料' }, { id: 'review', label: '全书检查' },
]
export function ProjectLayout({ children }: { children: ReactNode }) {
  const { state, actions } = useApp(); const { project } = useActiveProject(); const city = useIllustration(project.art)
  return <div className="project-shell">
    <header className="projectbar" style={{ backgroundImage: `linear-gradient(90deg,#fff 70%,rgba(255,255,255,.25)),url(${city})` }}>
      <button className="project-title" onClick={() => actions.navigate('projects')}><ArrowLeft/>{project.title}</button>
      <span className="autosave"><CircleCheck size={15}/> 自动保存中&nbsp; 14:32:05</span>
      <nav aria-label="作品内导航"><button className={state.projectSection === 'overview' ? 'active' : ''} onClick={() => actions.setProjectSection('overview')}>作品概览</button>{items.map((item) => <button key={item.id} className={state.projectSection === item.id ? 'active' : ''} onClick={() => actions.setProjectSection(item.id)}>{item.label}</button>)}</nav>
    </header>
    <div className="project-content">{children}</div>
  </div>
}
