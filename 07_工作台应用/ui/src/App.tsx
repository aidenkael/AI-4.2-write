import { AppProvider, useApp } from './features/app/AppStore'
import { FormalProjectShellProvider } from './features/projects/FormalProjectShell'
import { AuthorTaskCoordinatorProvider } from './features/tasks/AuthorTaskCoordinator'
import { AppShell } from './layouts/AppShell'
import { ProjectLayout } from './layouts/ProjectLayout'
import { HomePage } from './pages/HomePage'
import { ProjectsPage } from './pages/ProjectsPage'
import { MaterialsPage } from './pages/MaterialsPage'
import { IdeasPage } from './pages/IdeasPage'
import { SettingsFeature } from './features/settings/SettingsFeature'
import { DevelopmentPage } from './pages/DevelopmentPage'
import { WritingPage } from './pages/WritingPage'
import { StoryMapPage } from './pages/StoryMapPage'
import { ProjectDataPage } from './pages/ProjectDataPage'
import { ReviewPage } from './pages/ReviewPage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import type { ProjectSection } from './contracts/ui'
import './styles.css'

// 正式项目外壳已接入全部作品内页面（overview / development / writing /
// map / data / review）；所有页面都使用同一正式 project_id，禁止 Mock 身份。
const CONNECTED_SECTIONS: readonly ProjectSection[] = ['overview', 'development', 'writing', 'map', 'data', 'review']

function Router() {
  const { state } = useApp()
  const globalPages = { home: <HomePage />, projects: <ProjectsPage />, materials: <MaterialsPage />, ideas: <IdeasPage />, settings: <SettingsFeature /> }
  const projectPages: Record<ProjectSection, JSX.Element> = { overview: <ProjectOverviewPage />, development: <DevelopmentPage />, writing: <WritingPage />, map: <StoryMapPage />, data: <ProjectDataPage />, review: <ReviewPage /> }
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
