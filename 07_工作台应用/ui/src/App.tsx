import { useState } from 'react'
import HomePage from './pages/HomePage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectOverviewPage from './pages/ProjectOverviewPage'
import SettingsPage from './pages/SettingsPage'

const NAV_ITEMS = ['首页', '我的作品', '素材与学习', '灵感箱', '搜索', '设置']

export type Page =
  | { kind: 'home' }
  | { kind: 'projects' }
  | { kind: 'overview'; projectId: string; projectName: string }
  | { kind: 'settings' }

export default function App() {
  const [page, setPage] = useState<Page>({ kind: 'home' })

  const navClick = (item: string) => {
    if (item === '首页') setPage({ kind: 'home' })
    else if (item === '我的作品') setPage({ kind: 'projects' })
    else if (item === '设置') setPage({ kind: 'settings' })
    // 其余导航项本轮不实现业务（占位）
  }

  return (
    <div style={{ fontFamily: 'system-ui, "Microsoft YaHei", sans-serif', padding: '1rem 1.5rem' }}>
      <h1>AI-write</h1>
      <nav style={{ display: 'flex', gap: '1.25rem', margin: '0.5rem 0 1rem' }}>
        {NAV_ITEMS.map((item) => (
          <span key={item} style={{ cursor: 'pointer' }} onClick={() => navClick(item)}>
            {item}
          </span>
        ))}
      </nav>
      <hr />
      {page.kind === 'home' && <HomePage />}
      {page.kind === 'projects' && (
        <ProjectsPage
          onOpen={(p) => setPage({ kind: 'overview', projectId: p.project_id, projectName: p.name })}
        />
      )}
      {page.kind === 'overview' && (
        <ProjectOverviewPage
          projectId={page.projectId}
          projectName={page.projectName}
          onBack={() => setPage({ kind: 'projects' })}
        />
      )}
      {page.kind === 'settings' && <SettingsPage />}
    </div>
  )
}
