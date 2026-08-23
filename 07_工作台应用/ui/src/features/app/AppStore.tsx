import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Candidate, GlobalPage, IllustrationKey, Idea, ProjectSection, ReviewIssue, WorkStatus } from '../../contracts/ui'
import { defaultIllustrations } from '../../assets/illustrations'
import { chapters as seedChapters, reviewIssues as seedReviewIssues, seedIdeas } from '../../mock/data'
import { mockService } from '../../mock/service'

interface AppState {
  page: GlobalPage; projectSection: ProjectSection | null; activeProjectId: string; activeChapterId: string
  chapters: typeof seedChapters; ideas: Idea[]; developmentStatus: WorkStatus; candidates: Candidate[]; acceptedCandidateId: string | null
  writingStatus: WorkStatus; proseCandidate: string; prosePrompt: string; reviews: ReviewIssue[]
  illustrations: { defaults: Record<IllustrationKey, string>; custom: Partial<Record<IllustrationKey, string>> }
  search: string; toast: string | null; dialog: { title: string; content: string } | null; preferences: Record<string, boolean>
}
interface Actions {
  navigate(page: GlobalPage): void; openProject(id?: string, section?: ProjectSection): void; setProjectSection(section: ProjectSection): void
  setChapter(id: string): void; addChapter(): void; updateChapter(content: string): void; createIdea(content: string, kind?: Idea['kind']): Promise<void>; toggleIdea(id: string): void
  brainstorm(input: string): Promise<void>; acceptCandidate(id: string): void; dismissCandidates(): void
  setProsePrompt(value: string): void; generateProse(prompt?: string): Promise<void>; editProse(value: string): void; acceptProse(): void; discardProse(): void
  toggleReview(id: string): void; resolveReview(id: string): void; setIllustration(key: IllustrationKey, url: string): void; resetIllustration(key: IllustrationKey): void
  setSearch(value: string): void; notify(message: string): void; openDialog(title: string, content: string): void; closeDialog(): void; setPreference(key: string, value: boolean): void
}
const initial: AppState = {
  page: 'home', projectSection: null, activeProjectId: 'mist', activeChapterId: '18', chapters: seedChapters,
  ideas: seedIdeas, developmentStatus: 'idle', candidates: [], acceptedCandidateId: null,
  writingStatus: 'idle', proseCandidate: '', prosePrompt: '', reviews: seedReviewIssues,
  illustrations: { defaults: defaultIllustrations, custom: {} },
  search: '', toast: null, dialog: null, preferences: { autosave: true, sound: false, compactMap: false },
}
const Context = createContext<{ state: AppState; actions: Actions } | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initial)
  const actions = useMemo<Actions>(() => ({
    navigate(page) { setState((s) => ({ ...s, page, projectSection: null })) },
    openProject(id = 'mist', section = 'development') { setState((s) => ({ ...s, activeProjectId: id, projectSection: section })) },
    setProjectSection(projectSection) { setState((s) => ({ ...s, projectSection })) },
    setChapter(activeChapterId) { setState((s) => ({ ...s, activeChapterId })) },
    addChapter() { setState((s) => { const next = String(Math.max(...s.chapters.map((chapter) => Number(chapter.id) || 0)) + 1); return { ...s, activeChapterId: next, chapters: [...s.chapters, { id: next, title: `第${next}章　新的章节`, words: 0, content: '' }] } }) },
    updateChapter(content) { setState((s) => ({ ...s, chapters: s.chapters.map((c) => c.id === s.activeChapterId ? { ...c, content, words: content.length } : c) })) },
    async createIdea(content, kind) { if (!content.trim()) return; const idea = await mockService.createIdea(content.trim(), kind); setState((s) => ({ ...s, ideas: [idea, ...s.ideas] })) },
    toggleIdea(id) { setState((s) => ({ ...s, ideas: s.ideas.map((i) => i.id === id ? { ...i, used: !i.used } : i) })) },
    async brainstorm(input) {
      if (!input.trim()) return
      setState((s) => ({ ...s, developmentStatus: 'running', candidates: [], acceptedCandidateId: null }))
      try { const candidates = await mockService.generateCandidates(input.trim()); setState((s) => ({ ...s, developmentStatus: 'waiting_confirmation', candidates })) }
      catch { setState((s) => ({ ...s, developmentStatus: 'failed' })) }
    },
    acceptCandidate(id) { setState((s) => ({ ...s, acceptedCandidateId: id, developmentStatus: 'accepted', candidates: s.candidates.map((c) => ({ ...c, status: c.id === id ? 'accepted' : 'candidate' })) })) },
    dismissCandidates() { setState((s) => ({ ...s, candidates: [], developmentStatus: 'idle', acceptedCandidateId: null })) },
    setProsePrompt(prosePrompt) { setState((s) => ({ ...s, prosePrompt })) },
    async generateProse(prompt) {
      const request = prompt ?? state.prosePrompt
      setState((s) => ({ ...s, writingStatus: 'running', proseCandidate: '' }))
      try { const proseCandidate = await mockService.generateProse(request); setState((s) => ({ ...s, proseCandidate, prosePrompt: request, writingStatus: 'waiting_confirmation' })) }
      catch { setState((s) => ({ ...s, writingStatus: 'failed' })) }
    },
    editProse(proseCandidate) { setState((s) => ({ ...s, proseCandidate })) },
    acceptProse() { setState((s) => ({ ...s, chapters: s.chapters.map((c) => c.id === s.activeChapterId ? { ...c, content: `${c.content}\n\n${s.proseCandidate}`, words: c.words + s.proseCandidate.length } : c), writingStatus: 'accepted', prosePrompt: '' })) },
    discardProse() { setState((s) => ({ ...s, proseCandidate: '', writingStatus: 'idle' })) },
    toggleReview(id) { setState((s) => ({ ...s, reviews: s.reviews.map((r) => r.id === id ? { ...r, open: !r.open } : r) })) },
    resolveReview(id) { setState((s) => ({ ...s, reviews: s.reviews.map((r) => r.id === id ? { ...r, resolved: true, category: 'clear' } : r) })) },
    setIllustration(key, url) { setState((s) => ({ ...s, illustrations: { ...s.illustrations, custom: { ...s.illustrations.custom, [key]: url } } })) },
    resetIllustration(key) { setState((s) => { const custom = { ...s.illustrations.custom }; delete custom[key]; return { ...s, illustrations: { ...s.illustrations, custom } } }) },
    setSearch(search) { setState((s) => ({ ...s, search })) },
    notify(message) { setState((s) => ({ ...s, toast: message })); window.setTimeout(() => setState((s) => s.toast === message ? { ...s, toast: null } : s), 2600) },
    openDialog(title, content) { setState((s) => ({ ...s, dialog: { title, content } })) },
    closeDialog() { setState((s) => ({ ...s, dialog: null })) },
    setPreference(key, value) { setState((s) => ({ ...s, preferences: { ...s.preferences, [key]: value } })) },
  }), [state.prosePrompt])
  return <Context.Provider value={{ state, actions }}>{children}</Context.Provider>
}

export function useApp() { const value = useContext(Context); if (!value) throw new Error('useApp must be inside AppProvider'); return value }
export function useIllustration(key: IllustrationKey) { const { state } = useApp(); return state.illustrations.custom[key] ?? state.illustrations.defaults[key] }
