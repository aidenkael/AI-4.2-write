import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Candidate, Chapter, GlobalPage, IllustrationKey, Idea, Material, Project, ProjectDataRecord, ProjectSection, ReviewIssue, WorkStatus } from '../../contracts/ui'
import { defaultIllustrations } from '../../assets/illustrations'
import { chapters as seedChapters, characters, materials as seedMaterials, projects as seedProjects, reviewIssues as seedReviewIssues, seedIdeas } from '../../mock/data'
import { mockService } from '../../mock/service'

interface ProjectMockState {
  activeChapterId: string; chapters: Chapter[]; developmentStatus: WorkStatus; candidates: Candidate[]; acceptedCandidateId: string | null
  writingStatus: WorkStatus; proseCandidate: string; prosePrompt: string; reviews: ReviewIssue[]; data: ProjectDataRecord[]
}
interface AppState {
  page: GlobalPage; projectSection: ProjectSection | null; activeProjectId: string; projects: Project[]; projectStates: Record<string, ProjectMockState>
  materials: Material[]; ideas: Idea[]
  illustrations: { defaults: Record<IllustrationKey, string>; custom: Partial<Record<IllustrationKey, string>> }
  search: string; toast: string | null; dialog: { title: string; content: string } | null; preferences: Record<string, boolean>
}
interface Actions {
  navigate(page: GlobalPage): void; openProject(id: string, section?: ProjectSection): void; setProjectSection(section: ProjectSection): void; createProject(title: string, subtitle: string): string
  setChapter(id: string): void; addChapter(): void; updateChapter(content: string): void
  createIdea(content: string, kind?: Idea['kind']): Promise<void>; toggleIdea(id: string): void
  brainstorm(input: string): Promise<void>; acceptCandidate(id: string): void; dismissCandidates(): void
  setProsePrompt(value: string): void; generateProse(prompt?: string): Promise<void>; editProse(value: string): void; acceptProse(): void; discardProse(): void
  toggleReview(id: string): void; resolveReview(id: string): void
  createMaterial(input: Pick<Material, 'title' | 'type'>): string
  createProjectData(input: Pick<ProjectDataRecord, 'category' | 'title' | 'summary' | 'meta'>): string; editProjectData(id: string, changes: Pick<ProjectDataRecord, 'title' | 'summary'>): void
  setIllustration(key: IllustrationKey, url: string): void; resetIllustration(key: IllustrationKey): void
  setSearch(value: string): void; notify(message: string): void; openDialog(title: string, content: string): void; closeDialog(): void; setPreference(key: string, value: boolean): void
}

const makeData = (project: Project): ProjectDataRecord[] => ([...characters.map((character): ProjectDataRecord => ({ id: `${project.id}-${character.id}`, category: '人物', title: character.name, summary: character.note, meta: `出场：第 ${character.id === 'lu' ? '2' : '1'} 章`, role: character.role, identity: character.identity, status: character.status, relation: character.relation, note: character.note, color: character.color })),
  { id: `${project.id}-place`, category: '地点', title: project.id === 'mist' ? '雾城旧城区' : `${project.title}核心场景`, summary: '当前作品的重要叙事空间。', meta: '地点' },
  { id: `${project.id}-rule`, category: '世界与规则', title: `${project.title}世界规则`, summary: '当前作品已确认的基础世界规则。', meta: '世界规则' },
  { id: `${project.id}-event`, category: '重要事件', title: `${project.title}开端事件`, summary: '推动当前作品开始发展的关键事件。', meta: '第1章' },
  { id: `${project.id}-setting`, category: '已确认设定', title: `${project.title}核心设定`, summary: '作者已经确认、可供后续创作使用的设定。', meta: '设定' },
  { id: `${project.id}-note`, category: '项目资料', title: '章节节奏备忘', summary: '保持人物选择与情节推进并行。', meta: '项目资料' },
])
const makeChapters = (project: Project): Chapter[] => project.id === 'mist' ? seedChapters.map((chapter) => ({ ...chapter })) : project.chapter === 1 ? [
  { id: '1', title: '第1章　故事开端', words: project.words, content: `${project.subtitle}\n\n这是「${project.title}」独立保存的 Mock 正文。` },
] : [
  { id: '1', title: '第1章　故事开端', words: 860, content: `《${project.title}》从这里开始。`, done: true },
  { id: String(project.chapter), title: `第${project.chapter}章　当前章节`, words: project.words, content: `${project.subtitle}\n\n这是「${project.title}」独立保存的 Mock 正文。` },
]
const makeProjectState = (project: Project): ProjectMockState => ({
  activeChapterId: project.id === 'mist' ? '18' : String(project.chapter), chapters: makeChapters(project), developmentStatus: 'idle', candidates: [], acceptedCandidateId: null,
  writingStatus: 'idle', proseCandidate: '', prosePrompt: '', reviews: seedReviewIssues.map((issue) => ({ ...issue })), data: makeData(project),
})
const initialProjects = seedProjects.map((project) => ({ ...project }))
const initial: AppState = {
  page: 'home', projectSection: null, activeProjectId: 'mist', projects: initialProjects,
  projectStates: Object.fromEntries(initialProjects.map((project) => [project.id, makeProjectState(project)])),
  materials: seedMaterials.map((material) => ({ ...material, knowledge: [...material.knowledge] })),
  ideas: seedIdeas.map((idea) => ({ ...idea })), illustrations: { defaults: defaultIllustrations, custom: {} },
  search: '', toast: null, dialog: null, preferences: { autosave: true, sound: false, compactMap: false },
}
const Context = createContext<{ state: AppState; actions: Actions } | null>(null)

const updateProject = (state: AppState, projectId: string, update: (project: ProjectMockState) => ProjectMockState): AppState => ({ ...state, projectStates: { ...state.projectStates, [projectId]: update(state.projectStates[projectId]) } })

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initial)
  const activeProjectState = state.projectStates[state.activeProjectId]
  const actions = useMemo<Actions>(() => ({
    navigate(page) { setState((current) => ({ ...current, page, projectSection: null })) },
    openProject(activeProjectId, projectSection = 'overview') { setState((current) => current.projectStates[activeProjectId] ? { ...current, activeProjectId, projectSection } : current) },
    setProjectSection(projectSection) { setState((current) => ({ ...current, projectSection })) },
    createProject(title, subtitle) {
      const id = `mock-${crypto.randomUUID()}`; const project: Project = { id, title, subtitle, chapter: 1, words: 0, updated: '刚刚', status: '构思中', art: 'city' }
      setState((current) => ({ ...current, projects: [...current.projects, project], projectStates: { ...current.projectStates, [id]: makeProjectState(project) }, activeProjectId: id, projectSection: 'overview' })); return id
    },
    setChapter(activeChapterId) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, activeChapterId }))) },
    addChapter() { setState((current) => updateProject(current, current.activeProjectId, (project) => { const next = String(Math.max(...project.chapters.map((chapter) => Number(chapter.id) || 0)) + 1); return { ...project, activeChapterId: next, chapters: [...project.chapters, { id: next, title: `第${next}章　新的章节`, words: 0, content: '' }] } })) },
    updateChapter(content) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, chapters: project.chapters.map((chapter) => chapter.id === project.activeChapterId ? { ...chapter, content, words: content.length } : chapter) }))) },
    async createIdea(content, kind) { if (!content.trim()) return; const idea = await mockService.createIdea(content.trim(), kind); setState((current) => ({ ...current, ideas: [idea, ...current.ideas] })) },
    toggleIdea(id) { setState((current) => ({ ...current, ideas: current.ideas.map((idea) => idea.id === id ? { ...idea, used: !idea.used } : idea) })) },
    async brainstorm(input) {
      if (!input.trim()) return; const projectId = state.activeProjectId
      setState((current) => updateProject(current, projectId, (project) => ({ ...project, developmentStatus: 'running', candidates: [], acceptedCandidateId: null })))
      try { const candidates = await mockService.generateCandidates(input.trim()); setState((current) => updateProject(current, projectId, (project) => ({ ...project, developmentStatus: 'waiting_confirmation', candidates }))) }
      catch { setState((current) => updateProject(current, projectId, (project) => ({ ...project, developmentStatus: 'failed' }))) }
    },
    acceptCandidate(id) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, acceptedCandidateId: id, developmentStatus: 'accepted', candidates: project.candidates.map((candidate) => ({ ...candidate, status: candidate.id === id ? 'accepted' : 'candidate' })) }))) },
    dismissCandidates() { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, candidates: [], developmentStatus: 'idle', acceptedCandidateId: null }))) },
    setProsePrompt(prosePrompt) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, prosePrompt }))) },
    async generateProse(prompt) {
      const projectId = state.activeProjectId; const request = prompt ?? activeProjectState.prosePrompt
      setState((current) => updateProject(current, projectId, (project) => ({ ...project, writingStatus: 'running', proseCandidate: '' })))
      try { const proseCandidate = await mockService.generateProse(request); setState((current) => updateProject(current, projectId, (project) => ({ ...project, proseCandidate, prosePrompt: request, writingStatus: 'waiting_confirmation' }))) }
      catch { setState((current) => updateProject(current, projectId, (project) => ({ ...project, writingStatus: 'failed' }))) }
    },
    editProse(proseCandidate) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, proseCandidate }))) },
    acceptProse() { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, chapters: project.chapters.map((chapter) => chapter.id === project.activeChapterId ? { ...chapter, content: `${chapter.content}\n\n${project.proseCandidate}`, words: chapter.words + project.proseCandidate.length } : chapter), writingStatus: 'accepted', prosePrompt: '' }))) },
    discardProse() { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, proseCandidate: '', writingStatus: 'idle' }))) },
    toggleReview(id) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, reviews: project.reviews.map((issue) => issue.id === id ? { ...issue, open: !issue.open } : issue) }))) },
    resolveReview(id) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, reviews: project.reviews.map((issue) => issue.id === id ? { ...issue, resolved: true, category: 'clear' } : issue) }))) },
    createMaterial({ title, type }) { const id = `material-${crypto.randomUUID()}`; const material: Material = { id, title, type, status: type === '专题研究' ? '处理中' : '需要处理', date: '刚刚', summary: '新建的 Mock 素材，等待继续整理。', knowledge: ['等待提炼的知识点'] }; setState((current) => ({ ...current, materials: [material, ...current.materials] })); return id },
    createProjectData(input) { const id = `data-${crypto.randomUUID()}`; setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, data: [{ id, ...input }, ...project.data] }))); return id },
    editProjectData(id, changes) { setState((current) => updateProject(current, current.activeProjectId, (project) => ({ ...project, data: project.data.map((record) => record.id === id ? { ...record, ...changes } : record) }))) },
    setIllustration(key, url) { setState((current) => ({ ...current, illustrations: { ...current.illustrations, custom: { ...current.illustrations.custom, [key]: url } } })) },
    resetIllustration(key) { setState((current) => { const custom = { ...current.illustrations.custom }; delete custom[key]; return { ...current, illustrations: { ...current.illustrations, custom } } }) },
    setSearch(search) { setState((current) => ({ ...current, search })) },
    notify(message) { setState((current) => ({ ...current, toast: message })); window.setTimeout(() => setState((current) => current.toast === message ? { ...current, toast: null } : current), 2600) },
    openDialog(title, content) { setState((current) => ({ ...current, dialog: { title, content } })) },
    closeDialog() { setState((current) => ({ ...current, dialog: null })) },
    setPreference(key, value) { setState((current) => ({ ...current, preferences: { ...current.preferences, [key]: value } })) },
  }), [activeProjectState.prosePrompt, state.activeProjectId])
  return <Context.Provider value={{ state, actions }}>{children}</Context.Provider>
}

export function useApp() { const value = useContext(Context); if (!value) throw new Error('useApp must be inside AppProvider'); return value }
export function useActiveProject() { const { state } = useApp(); return { project: state.projects.find((project) => project.id === state.activeProjectId)!, projectState: state.projectStates[state.activeProjectId] } }
export function useIllustration(key: IllustrationKey) { const { state } = useApp(); return state.illustrations.custom[key] ?? state.illustrations.defaults[key] }
