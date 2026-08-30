import { AppProvider, useApp } from './features/app/AppStore'
import { FormalProjectShellProvider } from './features/projects/FormalProjectShell'
import { AuthorTaskCoordinatorProvider } from './features/tasks/AuthorTaskCoordinator'
import { AppShell } from './layouts/AppShell'
import { ProjectLayout } from './layouts/ProjectLayout'
import { WorksPage } from './pages/WorksPage'
import { MaterialsPage } from './pages/MaterialsPage'
import { IdeasPage } from './pages/IdeasPage'
import { SettingsFeature } from './features/settings/SettingsFeature'
import { PlanningPage } from './pages/PlanningPage'
import { WritingPage } from './pages/WritingPage'
import { StoryMapPage } from './pages/StoryMapPage'
import { FoundationPage } from './pages/FoundationPage'
import { ReviewPage } from './pages/ReviewPage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import type { ProjectSection } from './contracts/ui'
import './styles.css'

// Go Write 2.0 作者面：全局四入口（作品 / 素材与学习 / 灵感箱 / 设置）+
// 作品内六任务（概览 / 地基 / 规划 / 正在写 / 地图 / 检查）。
// 正式项目外壳已接入全部作品内页面；所有页面都使用同一正式 project_id，禁止 Mock 身份。
const CONNECTED_SECTIONS: readonly ProjectSection[] = ['overview', 'foundation', 'planning', 'writing', 'map', 'review']

function Router() {
  const { state } = useApp()
  const globalPages = { works: <WorksPage />, materials: <MaterialsPage />, ideas: <IdeasPage />, settings: <SettingsFeature /> }
  const projectPages: Record<ProjectSection, JSX.Element> = { overview: <ProjectOverviewPage />, foundation: <FoundationPage />, planning: <PlanningPage />, writing: <WritingPage />, map: <StoryMapPage />, review: <ReviewPage /> }
  const section = state.projectSection
  const safeSection = section && CONNECTED_SECTIONS.includes(section) ? section : null
  const content = safeSection ? <ProjectLayout>{projectPages[safeSection]}</ProjectLayout> : globalPages[state.page]
  return <AppShell>{content}</AppShell>
}

export default function App() {
  return (
    <AppProvider>
      <FormalProjectShellProvider>
        {/* App 级任务协调器：位于 Router 之上——导航/页面卸载绝不取消或孤立任务 */}
        <AuthorTaskCoordinatorProvider>
          <Router />
        </AuthorTaskCoordinatorProvider>
      </FormalProjectShellProvider>
    </AppProvider>
  )
}
