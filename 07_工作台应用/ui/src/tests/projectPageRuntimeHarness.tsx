import { Component, type ReactElement } from 'react'
import { act, create } from 'react-test-renderer'
import { ProjectLayout } from '../layouts/ProjectLayout'
import { ProjectOverviewPage } from '../pages/ProjectOverviewPage'
import { FoundationPage } from '../pages/FoundationPage'
import { PlanningPage } from '../pages/PlanningPage'
import { WritingPage } from '../pages/WritingPage'
import { StoryMapPage } from '../pages/StoryMapPage'
import { ReviewPage } from '../pages/ReviewPage'
import { AppContext, type Actions, type AppState } from '../features/app/AppStore'
import { FormalProjectShellContext, type FormalProjectShellValue } from '../features/projects/FormalProjectShell'
import { AuthorTaskContext, type AuthorTaskController } from '../features/tasks/AuthorTaskCoordinator'
import { BridgeError, type ProjectData, validateProjectData } from '../bridge/client'

const projectId = 'proj_runtime_smoke'
const settlement = { status: 'synchronized' as const, pending_count: 0, failed_count: 0, changes: [] }
const sections = {
  characters: [], relationships: [], canon_facts: [], locations: [], organizations: [], systems: [],
  occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], mystery_information: [], approved_plan: [],
}

export const minimalProjectData: ProjectData = {
  project_id: projectId, name: '运行时烟测作品', state_rev: 0, model_rev: 0, last_authority_source: null,
  work_direction: '', reader_promise: '', settlement,
  story_bible_profile: { genre_tags: [], narrative_mode: null, active_modules: ['core', 'characters', 'relationships', 'world', 'locations', 'organizations', 'storylines', 'foreshadowing', 'events', 'time'], field_config: {} },
  length_plan: { total_target_words: null, actual_total_words: 0, stages: [], chapters: [] },
  chapters: [], planning_impact_candidates: [], retired: { foundation: [], relationships: [] }, sections,
}

const actions: Actions = {
  navigate: () => {}, setProjectSection: () => {}, setSearch: () => {}, notify: () => {}, openDialog: () => {}, closeDialog: () => {},
  setPreference: () => {}, setIllustration: () => {}, resetIllustration: () => {}, setPlanningPrefill: () => {}, consumePlanningPrefill: () => null,
  setReviewChapterHandoff: () => {}, consumeReviewChapterHandoff: () => null, setFoundationEditHandoff: () => {}, consumeFoundationEditHandoff: () => null,
}
const appState: AppState = { page: 'works', projectSection: 'overview', illustrations: { defaults: { city: '', mountains: '', desk: '' }, custom: {} }, search: '', toast: null, dialog: null, preferences: { sound: false }, planningPrefill: null, reviewChapterHandoff: null, foundationEditHandoff: null }
const formal: FormalProjectShellValue = {
  projects: [{ project_id: projectId, name: '运行时烟测作品' }], selected: { project_id: projectId, name: '运行时烟测作品' }, loading: false, error: null,
  reload: async () => {}, openProjectById: async () => true, clearSelection: () => {},
}
const tasks: AuthorTaskController = {
  task: null, start: async () => null, cancel: async () => {}, confirm: async () => null, consume: () => {}, navigateToTask: () => {}, resume: async () => {},
}

function bridgeData(method: string): unknown {
  if (method === 'get_project_data') return minimalProjectData
  if (method === 'get_project_overview') return { project_id: projectId, name: '运行时烟测作品', state: { state_rev: 0, last_authority_source: '' }, current_plans: [], progress: { current_chapter: 1, actual_words: 0, target_words: null }, settlement }
  if (method === 'get_story_write_surface') return { project_id: projectId, name: '运行时烟测作品', chapters: [], active_chapter_number: 1, total_words: 0, settlement, open_threads: [] }
  if (method === 'get_review_surface') return { project_id: projectId, name: '运行时烟测作品', active_plan_count: 0, open_thread_count: 0, chapters: [], latest_chapter_number: null, has_accepted_prose: false, settlement }
  return null
}

function installBridge() {
  const target = globalThis as unknown as { window?: unknown; IS_REACT_ACT_ENVIRONMENT?: boolean }
  const previous = target.window
  target.IS_REACT_ACT_ENVIRONMENT = true
  target.window = {
    pywebview: { api: new Proxy({}, { get: (_target, method) => (method === 'then' ? undefined : async () => ({ ok: true, data: bridgeData(String(method)), error: null })) }) },
    setTimeout, clearTimeout, setInterval, clearInterval, addEventListener: () => {}, removeEventListener: () => {},
  }
  return () => { target.window = previous }
}

function wrap(page: ReactElement) {
  return <AppContext.Provider value={{ state: appState, actions }}><FormalProjectShellContext.Provider value={formal}><AuthorTaskContext.Provider value={tasks}><ProjectLayout>{page}</ProjectLayout></AuthorTaskContext.Provider></FormalProjectShellContext.Provider></AppContext.Provider>
}

export async function mountAllProjectPages(): Promise<void> {
  const restore = installBridge()
  try {
    for (const Page of [ProjectOverviewPage, FoundationPage, PlanningPage, WritingPage, StoryMapPage, ReviewPage]) {
      const holder: { renderer: ReturnType<typeof create> | null } = { renderer: null }
      await act(async () => { holder.renderer = create(wrap(<Page />)); await Promise.resolve(); await Promise.resolve() })
      holder.renderer?.unmount()
    }
  } finally {
    restore()
  }
}

class CrashPage extends Component { render(): ReactElement { throw new Error('smoke crash') } }

export async function errorBoundaryKeepsProjectNavigation(): Promise<boolean> {
  const restore = installBridge()
  const originalError = console.error
  console.error = () => {}
  try {
    const holder: { renderer: ReturnType<typeof create> | null } = { renderer: null }
    await act(async () => { holder.renderer = create(wrap(<CrashPage />)); await Promise.resolve() })
    const output = JSON.stringify(holder.renderer?.toJSON())
    return output.includes('作品概览') && output.includes('这个页面加载失败，请刷新后重试。')
  } finally {
    console.error = originalError
    restore()
  }
}

export function invalidProjectDataIsRejected(): boolean {
  const invalid = { ...minimalProjectData, length_plan: undefined }
  try {
    validateProjectData(invalid)
    return false
  } catch (error) {
    return error instanceof BridgeError && error.code === 'PROJECT_DATA_INVALID'
  }
}

export function minimalProjectDataPassesContract(): boolean {
  return validateProjectData(minimalProjectData).project_id === minimalProjectData.project_id
}

export function missingRetiredSurfaceIsRejected(): boolean {
  const invalid = { ...minimalProjectData, retired: undefined }
  try {
    validateProjectData(invalid)
    return false
  } catch (error) {
    return error instanceof BridgeError && error.code === 'PROJECT_DATA_INVALID'
  }
}

/** Retired records render in a compact 已退役 area with a 恢复 action (Foundation page). */
export async function retiredRecordsRenderWithRestoreAction(): Promise<boolean> {
  const retiredEntry = {
    id: 'gw_retired_1', label: '退役人物', record: { name: '退役人物' },
    source_ref: 'gw_retired_1', source_kind: 'author_workspace', category: 'character', editable: true,
  }
  const dataWithRetired: ProjectData = {
    ...minimalProjectData,
    retired: { foundation: [retiredEntry], relationships: [] },
  }
  const target = globalThis as unknown as { window?: unknown; IS_REACT_ACT_ENVIRONMENT?: boolean }
  const previous = target.window
  target.IS_REACT_ACT_ENVIRONMENT = true
  target.window = {
    pywebview: {
      api: new Proxy({}, {
        get: (_t, method) => (method === 'then' ? undefined : async () => ({
          ok: true,
          data: method === 'get_project_data' ? dataWithRetired : bridgeData(String(method)),
          error: null,
        })),
      }),
    },
    setTimeout, clearTimeout, setInterval, clearInterval, addEventListener: () => {}, removeEventListener: () => {},
  }
  try {
    const holder: { renderer: ReturnType<typeof create> | null } = { renderer: null }
    let output = ''
    await act(async () => {
      holder.renderer = create(wrap(<FoundationPage />))
      await Promise.resolve(); await Promise.resolve()
    })
    // Bridge 加载是异步的：多拍几次微任务，等待 setData 触发重渲染。
    for (let i = 0; i < 8; i += 1) {
      await act(async () => { await Promise.resolve() })
    }
    output = JSON.stringify(holder.renderer?.toJSON())
    holder.renderer?.unmount()
    return output.includes('已退役') && output.includes('恢复') && output.includes('退役人物')
  } finally {
    target.window = previous
  }
}
