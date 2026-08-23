import type { ReactNode } from 'react'
import { BookOpen, ChevronDown, Feather, Folder, Home, Lightbulb, Search, Settings } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import type { GlobalPage } from '../contracts/ui'

const nav: Array<{ id: GlobalPage; label: string; Icon: typeof Home }> = [
  { id: 'home', label: '首页', Icon: Home }, { id: 'projects', label: '我的作品', Icon: Folder },
  { id: 'materials', label: '素材与学习', Icon: BookOpen }, { id: 'ideas', label: '灵感箱', Icon: Lightbulb },
]
export function AppShell({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const active = state.projectSection ? 'projects' : state.page
  return <div className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => actions.navigate('home')}><Feather size={30} fill="currentColor"/><strong>AI-write</strong></button>
      <nav className="global-nav" aria-label="全局导航">{nav.map(({ id, label, Icon }) => <button key={id} className={active === id ? 'active' : ''} onClick={() => actions.navigate(id)}><Icon/><span>{label}</span></button>)}</nav>
      <label className="search"><Search size={19}/><input aria-label="搜索" placeholder={active === 'ideas' ? '搜索灵感' : '搜索'}/></label>
      <button className={`settings-link ${active === 'settings' ? 'active' : ''}`} onClick={() => actions.navigate('settings')}><Settings/> <span>设置</span></button>
      <button className="user"><span>作</span><ChevronDown size={16}/></button>
    </header>
    <main>{children}</main>
  </div>
}
