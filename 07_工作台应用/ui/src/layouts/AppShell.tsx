import type { ReactNode } from 'react'
import { BookOpen, ChevronDown, Feather, Folder, Home, Lightbulb, Search, Settings, X } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import type { GlobalPage } from '../contracts/ui'

const nav: Array<{ id: GlobalPage; label: string; Icon: typeof Home }> = [
  { id: 'home', label: '首页', Icon: Home }, { id: 'projects', label: '我的作品', Icon: Folder },
  { id: 'materials', label: '素材与学习', Icon: BookOpen }, { id: 'ideas', label: '灵感箱', Icon: Lightbulb },
]
export function AppShell({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const active = state.projectSection ? 'projects' : state.page
  const results = [
    ...state.projects.map((project) => ({ label: project.title, run: () => actions.openProject(project.id, 'overview') })),
    { label: '素材与学习', run: () => actions.navigate('materials') },
    { label: '灵感箱', run: () => actions.navigate('ideas') },
    { label: '全书检查', run: () => actions.openProject(state.activeProjectId, 'review') },
  ].filter((item) => item.label.includes(state.search.trim()))
  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => actions.navigate('home')}><Feather size={30} fill="currentColor"/><strong>AI-write</strong></button>
      <nav className="global-nav" aria-label="全局导航">{nav.map(({ id, label, Icon }) => <button key={id} className={active === id ? 'active' : ''} onClick={() => actions.navigate(id)}><Icon/><span>{label}</span></button>)}</nav>
      <div className="search-wrap"><label className="search"><Search size={19}/><input aria-label="搜索" value={state.search} onChange={(e) => actions.setSearch(e.target.value)} placeholder={active === 'ideas' ? '搜索灵感' : '搜索'}/></label>
        {state.search.trim() && <div className="search-results" role="listbox">{results.length ? results.map((item) => <button key={item.label} onClick={() => { item.run(); actions.setSearch('') }}>{item.label}</button>) : <p>没有匹配的工作台入口</p>}</div>}
      </div>
      <button className={`settings-link ${active === 'settings' ? 'active' : ''}`} onClick={() => actions.navigate('settings')}><Settings/> <span>设置</span></button>
      <button className="user" onClick={() => actions.openDialog('作者账户', '当前为本地 Mock 作者账户。账户与同步将在正式应用层接入。')}><span>作</span><ChevronDown size={16}/></button>
    </header>
    <main>{children}</main>
    {state.toast && <div className="toast" role="status">{state.toast}</div>}
    {state.dialog && <div className="dialog-backdrop" role="presentation" onMouseDown={actions.closeDialog}><section className="dialog panel" role="dialog" aria-modal="true" aria-label={state.dialog.title} onMouseDown={(event) => event.stopPropagation()}><header><h2>{state.dialog.title}</h2><button aria-label="关闭" onClick={actions.closeDialog}><X/></button></header><p>{state.dialog.content}</p><footer><button className="primary" onClick={actions.closeDialog}>知道了</button></footer></section></div>}
  </div>
}
