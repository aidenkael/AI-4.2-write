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
const stateRefresh = { status: 'synchronized' as const, pending_change_count: 0, awaiting_confirmation_count: 0, refresh_id: null, worker_active: false, summary: null, error: null }
const sections = {
  characters: [], relationships: [], canon_facts: [], locations: [], organizations: [], systems: [],
  occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], mystery_information: [], approved_plan: [],
}

export const minimalProjectData: ProjectData = {
  project_id: projectId, name: '运行时烟测作品', state_rev: 0, model_rev: 0, last_authority_source: null,
  work_direction: '', reader_promise: '', story_synopsis: '', settlement, state_refresh: stateRefresh,
  story_bible_profile: { genre_tags: [], narrative_mode: null, active_modules: ['core', 'characters', 'relationships', 'world', 'locations', 'organizations', 'storylines', 'foreshadowing', 'events', 'time'], field_config: {} },
  length_plan: { total_target_words: null, actual_total_words: 0, stages: [], chapters: [] },
  chapters: [], planning_impact_candidates: [], explicit_dependencies: [], retired: { foundation: [], relationships: [] }, sections,
}

const actions: Actions = {
  navigate: () => {}, setProjectSection: () => {}, setSearch: () => {}, notify: () => {}, openDialog: () => {}, closeDialog: () => {},
  setPreference: () => {}, setIllustration: async () => {}, resetIllustration: async () => {}, setPlanningPrefill: () => {}, consumePlanningPrefill: () => null,
  setReviewChapterHandoff: () => {}, consumeReviewChapterHandoff: () => null, setFoundationEditHandoff: () => {}, consumeFoundationEditHandoff: () => null,
  setFoundationDesignHandoff: () => {}, consumeFoundationDesignHandoff: () => null,
}
const appState: AppState = { page: 'works', projectSection: 'overview', illustrations: { defaults: { city: '', mountains: '', desk: '' }, custom: {} }, search: '', toast: null, dialog: null, preferences: { sound: false }, planningPrefill: null, reviewChapterHandoff: null, foundationEditHandoff: null, foundationDesignHandoff: null }
const formal: FormalProjectShellValue = {
  projects: [{ project_id: projectId, name: '运行时烟测作品' }], selected: { project_id: projectId, name: '运行时烟测作品' }, loading: false, error: null,
  reload: async () => {}, openProjectById: async () => true, clearSelection: () => {},
}
const tasks: AuthorTaskController = {
  task: null, start: async () => null, cancel: async () => {}, confirm: async () => null, consume: () => {}, navigateToTask: () => {}, resume: async () => {},
}

function bridgeData(method: string): unknown {
  if (method === 'get_project_data') return minimalProjectData
  if (method === 'get_project_state_refresh' || method === 'prepare_project_state_refresh') return stateRefresh
  if (method === 'get_project_overview') return { project_id: projectId, name: '运行时烟测作品', state: { state_rev: 0, last_authority_source: '' }, intent_rev: 1, story_synopsis: '', current_plans: [], progress: { current_chapter: 1, actual_words: 0, target_words: null }, open_items: { total: 0, items: [] }, primary_next_action: 'foundation', settlement }
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

/** Story Map creates through the same shared Foundation editors, without navigation handoff. */
export async function storyMapDirectCreateUsesSharedEditors(): Promise<boolean> {
  const characters = [
    { id: 'char-1', label: '人物甲', record: { name: '人物甲' }, source_ref: 'char-1', source_kind: 'author_workspace', category: 'character', status: 'current' as const, editable: true },
    { id: 'char-2', label: '人物乙', record: { name: '人物乙' }, source_ref: 'char-2', source_kind: 'author_workspace', category: 'character', status: 'current' as const, editable: true },
  ]
  const mapData: ProjectData = { ...minimalProjectData, sections: { ...minimalProjectData.sections, characters } }
  const target = globalThis as unknown as { window?: unknown; IS_REACT_ACT_ENVIRONMENT?: boolean }
  const previous = target.window
  target.IS_REACT_ACT_ENVIRONMENT = true
  target.window = {
    pywebview: { api: new Proxy({}, { get: (_t, method) => (method === 'then' ? undefined : async () => ({ ok: true, data: method === 'get_project_data' ? mapData : bridgeData(String(method)), error: null })) }) },
    setTimeout, clearTimeout, setInterval, clearInterval, addEventListener: () => {}, removeEventListener: () => {}, confirm: () => true,
  }
  try {
    const holder: { renderer: ReturnType<typeof create> | null } = { renderer: null }
    await act(async () => { holder.renderer = create(wrap(<StoryMapPage />)); await Promise.resolve(); await Promise.resolve() })
    for (let i = 0; i < 6; i += 1) await act(async () => { await Promise.resolve() })
    const renderer = holder.renderer
    if (!renderer) return false
    const buttonText = (node: { props: { children?: unknown } }) => {
      const children = Array.isArray(node.props.children) ? node.props.children : [node.props.children]
      return children.filter((child) => typeof child === 'string' || typeof child === 'number').join('')
    }
    const buttons = renderer.root.findAllByType('button')
    const addCharacter = buttons.find((button) => buttonText(button).includes('新增人物'))
    const addRelationship = buttons.find((button) => buttonText(button).includes('新增关系'))
    if (!addCharacter || !addRelationship || addRelationship.props.disabled) return false
    await act(async () => { addCharacter.props.onClick() })
    const characterEditor = renderer.root.findAll((node) => node.props['aria-label'] === '新增人物').length === 1
    await act(async () => { addRelationship.props.onClick() })
    const relationshipEditor = renderer.root.findAll((node) => node.props['aria-label'] === '新增关系').length === 1
    renderer.unmount()
    return characterEditor && relationshipEditor
  } finally {
    target.window = previous
  }
}
