import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { GlobalPage, IllustrationKey, IllustrationState, ProjectSection } from '../../contracts/ui'
import { defaultIllustrations } from '../../assets/illustrations'

/**
 * 收缩后的 AppStore：只保留 UI / 会话关注点。
 *
 * - 导航（page / projectSection；正式项目选择由 FormalProjectShell 持有，
 *   全局导航绝不清除它）
 * - toast / dialog（临时提示）
 * - 全局搜索（客户端过滤已加载正式实体的输入，见 AppShell）
 * - UI 偏好（会话级，非 Agent 执行配置；sound = 任务完成提示音，真实生效）
 * - 装饰性插图（不含任何假故事事实）
 * - 一次性 Development 预填（"帮我发展"项目内交接：session-only，消费即清，
 *   绝不持久化为 Canon，绝不是事件总线）
 * - 一次性 Review 章节交接（"检查这段"：session-only，消费即清，绝不自动运行）
 *
 * 明确移除：mock 项目 / 章节 / 素材 / 灵感 / 检查 / 资料数据与对应 service 方法。
 * 正式项目身份一律由 FormalProjectShell（后端 project_id）提供。
 */

interface DevelopmentPrefill {
  project_id: string
  text: string
}

interface ReviewChapterHandoff {
  project_id: string
  chapter_number: number
}

interface AppState {
  page: GlobalPage
  projectSection: ProjectSection | null
  illustrations: IllustrationState
  search: string
  toast: string | null
  dialog: { title: string; content: string } | null
  preferences: Record<string, boolean>
  developmentPrefill: DevelopmentPrefill | null
  reviewChapterHandoff: ReviewChapterHandoff | null
}

interface Actions {
  navigate(page: GlobalPage): void
  setProjectSection(section: ProjectSection): void
  setSearch(value: string): void
  notify(message: string): void
  openDialog(title: string, content: string): void
  closeDialog(): void
  setPreference(key: string, value: boolean): void
  setIllustration(key: IllustrationKey, url: string): void
  resetIllustration(key: IllustrationKey): void
  setDevelopmentPrefill(prefill: DevelopmentPrefill): void
  consumeDevelopmentPrefill(): DevelopmentPrefill | null
  setReviewChapterHandoff(handoff: ReviewChapterHandoff): void
  consumeReviewChapterHandoff(): ReviewChapterHandoff | null
}

const initial: AppState = {
  page: 'home',
  projectSection: null,
  illustrations: { defaults: defaultIllustrations, custom: {} },
  search: '',
  toast: null,
  dialog: null,
  preferences: { sound: false },
  developmentPrefill: null,
  reviewChapterHandoff: null,
}

const Context = createContext<{ state: AppState; actions: Actions } | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initial)
  const actions = useMemo<Actions>(() => ({
    navigate(page) { setState((current) => ({ ...current, page, projectSection: null })) },
    setProjectSection(projectSection) { setState((current) => ({ ...current, projectSection })) },
    setSearch(search) { setState((current) => ({ ...current, search })) },
    notify(message) { setState((current) => ({ ...current, toast: message })); window.setTimeout(() => setState((current) => current.toast === message ? { ...current, toast: null } : current), 2600) },
    openDialog(title, content) { setState((current) => ({ ...current, dialog: { title, content } })) },
    closeDialog() { setState((current) => ({ ...current, dialog: null })) },
    setPreference(key, value) { setState((current) => ({ ...current, preferences: { ...current.preferences, [key]: value } })) },
    setIllustration(key, url) { setState((current) => ({ ...current, illustrations: { ...current.illustrations, custom: { ...current.illustrations.custom, [key]: url } } })) },
    resetIllustration(key) { setState((current) => { const custom = { ...current.illustrations.custom }; delete custom[key]; return { ...current, illustrations: { ...current.illustrations, custom } } }) },
    setDevelopmentPrefill(developmentPrefill) { setState((current) => ({ ...current, developmentPrefill })) },
    consumeDevelopmentPrefill() {
      const value = state.developmentPrefill
      if (value) setState((current) => ({ ...current, developmentPrefill: null }))
      return value
    },
    setReviewChapterHandoff(reviewChapterHandoff) { setState((current) => ({ ...current, reviewChapterHandoff })) },
    consumeReviewChapterHandoff() {
      const value = state.reviewChapterHandoff
      if (value) setState((current) => ({ ...current, reviewChapterHandoff: null }))
      return value
    },
  }), [state.developmentPrefill, state.reviewChapterHandoff])
  return <Context.Provider value={{ state, actions }}>{children}</Context.Provider>
}

export function useApp() { const value = useContext(Context); if (!value) throw new Error('useApp must be inside AppProvider'); return value }
export function useIllustration(key: IllustrationKey) { const { state } = useApp(); return state.illustrations.custom[key] ?? state.illustrations.defaults[key] }
