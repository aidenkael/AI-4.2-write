import type { ReactNode } from 'react'
import { BookOpen, Feather, Folder, Lightbulb, Search, Settings, X } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { TaskStrip } from '../features/tasks/TaskStrip'
import type { GlobalPage } from '../contracts/ui'

const nav: Array<{ id: GlobalPage; label: string; Icon: typeof Folder }> = [
  { id: 'works', label: '作品', Icon: Folder },
  { id: 'materials', label: '素材与学习', Icon: BookOpen },
  { id: 'ideas', label: '灵感箱', Icon: Lightbulb },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const { projects, openProjectById } = useFormalProjectShell()
  // 作品内任何分区都属于全局「作品」入口；搜索保留为顶栏工具，不是第五个页面。
  const active: GlobalPage = state.projectSection ? 'works' : state.page
  const query = state.search.trim()

  // 全局搜索：客户端过滤已加载的正式实体（正式项目名 + 全局页面入口），不伪造结果。
  const projectResults = query
    ? projects.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
    : []
  const pageResults = query
    ? [...nav, { id: 'settings' as GlobalPage, label: '设置' }].filter((p) => p.label.includes(query))
    : []

  const openProjectResult = async (projectId: string) => {
    actions.setSearch('')
    const ok = await openProjectById(projectId)
    if (ok) actions.setProjectSection('overview')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => actions.navigate('works')}><Feather size={30} fill="currentColor" /><strong>AI-write</strong></button>
        <nav className="global-nav" aria-label="全局导航">{nav.map(({ id, label, Icon }) => <button key={id} className={active === id ? 'active' : ''} onClick={() => actions.navigate(id)}><Icon /><span>{label}</span></button>)}</nav>
        <div className="search-wrap">
          <label className="search"><Search size={19} /><input aria-label="搜索" value={state.search} onChange={(e) => actions.setSearch(e.target.value)} placeholder={active === 'ideas' ? '搜索灵感' : '搜索'} /></label>
          {query && (
            <div className="search-results" role="listbox">
              {projectResults.map((p) => (
                <button key={p.project_id} onClick={() => void openProjectResult(p.project_id)}>{p.name}</button>
              ))}
              {pageResults.map((p) => (
                <button key={p.id} onClick={() => { actions.navigate(p.id); actions.setSearch('') }}>{p.label}</button>
              ))}
              {projectResults.length === 0 && pageResults.length === 0 && <p>没有匹配的工作台入口</p>}
            </div>
          )}
        </div>
        <button className={`settings-link ${active === 'settings' ? 'active' : ''}`} onClick={() => actions.navigate('settings')}><Settings /> <span>设置</span></button>
      </header>
      <main>{children}</main>
      <TaskStrip />
      {state.toast && <div className="toast" role="status">{state.toast}</div>}
      {state.dialog && <div className="dialog-backdrop" role="presentation" onMouseDown={actions.closeDialog}><section className="dialog panel" role="dialog" aria-modal="true" aria-label={state.dialog.title} onMouseDown={(event) => event.stopPropagation()}><header><h2>{state.dialog.title}</h2><button aria-label="关闭" onClick={actions.closeDialog}><X /></button></header><p style={{ whiteSpace: 'pre-wrap' }}>{state.dialog.content}</p><footer><button className="primary" onClick={actions.closeDialog}>知道了</button></footer></section></div>}
    </div>
  )
}
