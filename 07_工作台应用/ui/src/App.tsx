import { AppProvider, useApp } from './features/app/AppStore'
import { AppShell } from './layouts/AppShell'
import { ProjectLayout } from './layouts/ProjectLayout'
import { HomePage } from './pages/HomePage'
import { ProjectsPage } from './pages/ProjectsPage'
import { MaterialsPage } from './pages/MaterialsPage'
import { IdeasPage } from './pages/IdeasPage'
import { SettingsPage } from './pages/SettingsPage'
import { DevelopmentPage } from './pages/DevelopmentPage'
import { WritingPage } from './pages/WritingPage'
import { StoryMapPage } from './pages/StoryMapPage'
import { ProjectDataPage } from './pages/ProjectDataPage'
import { ReviewPage } from './pages/ReviewPage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import './styles.css'

function Router() {
  const { state } = useApp()
  const globalPages = { home: <HomePage />, projects: <ProjectsPage />, materials: <MaterialsPage />, ideas: <IdeasPage />, settings: <SettingsPage /> }
  const projectPages = { overview: <ProjectOverviewPage />, development: <DevelopmentPage />, writing: <WritingPage />, map: <StoryMapPage />, data: <ProjectDataPage />, review: <ReviewPage /> }
  const content = state.projectSection ? <ProjectLayout>{projectPages[state.projectSection]}</ProjectLayout> : globalPages[state.page]
  return <AppShell>{content}</AppShell>
}

export default function App() { return <AppProvider><Router /></AppProvider> }
