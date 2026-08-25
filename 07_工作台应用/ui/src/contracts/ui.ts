export type WorkStatus = 'idle' | 'running' | 'candidate' | 'waiting_confirmation' | 'accepted' | 'failed'
export type GlobalPage = 'home' | 'projects' | 'materials' | 'ideas' | 'settings'
export type ProjectSection = 'overview' | 'development' | 'writing' | 'map' | 'data' | 'review'
export type IllustrationKey = 'city' | 'mountains' | 'desk'
export interface IllustrationState { defaults: Record<IllustrationKey, string>; custom: Partial<Record<IllustrationKey, string>> }
