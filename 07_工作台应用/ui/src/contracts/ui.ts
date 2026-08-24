export type WorkStatus = 'idle' | 'running' | 'candidate' | 'waiting_confirmation' | 'accepted' | 'failed'
export type GlobalPage = 'home' | 'projects' | 'materials' | 'ideas' | 'settings'
export type ProjectSection = 'overview' | 'development' | 'writing' | 'map' | 'data' | 'review'
export type IllustrationKey = 'city' | 'mountains' | 'desk'
export interface Project { id: string; title: string; subtitle: string; chapter: number; words: number; updated: string; status: string; art: IllustrationKey }
export interface Candidate { id: string; title: string; body: string; tone: string; status: WorkStatus }
export interface Chapter { id: string; title: string; words: number; content: string; done?: boolean }
export interface Material { id: string; title: string; type: string; status: string; date: string; summary: string; knowledge: string[] }
export interface ProjectDataRecord { id: string; category: string; title: string; summary: string; meta: string; role?: string; identity?: string; status?: string; relation?: string; note?: string; color?: string }
export interface Idea { id: string; kind: '场景' | '对白' | '链接' | '文件'; content: string; note: string; time: string; used: boolean }
export interface Character { id: string; name: string; role: string; identity: string; status: string; relation: string; note: string; color: string }
export interface ReviewIssue { id: string; category: 'priority' | 'watch' | 'clear'; title: string; detail: string; count?: number; resolved: boolean; open: boolean }
export interface IllustrationState { defaults: Record<IllustrationKey, string>; custom: Partial<Record<IllustrationKey, string>> }
export interface MockWorkbenchService { simulate<T>(value: T, delay?: number): Promise<T>; createIdea(content: string, kind?: Idea['kind']): Promise<Idea>; generateCandidates(input: string): Promise<Candidate[]>; generateProse(prompt: string): Promise<string> }
