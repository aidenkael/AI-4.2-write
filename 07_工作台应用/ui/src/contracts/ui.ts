export type WorkStatus = 'idle' | 'running' | 'candidate' | 'waiting_confirmation' | 'accepted' | 'failed'
/** 全局导航：作品（统一落地页）/ 素材与学习 / 灵感箱 / 设置；搜索是顶栏工具，不是页面。 */
export type GlobalPage = 'works' | 'materials' | 'ideas' | 'settings'
/** 作品内六任务：概览 / 地基 / 规划 / 正在写 / 地图 / 检查。后端操作名不变（foundation 仍消费 get_project_data，planning 仍走 StoryPlan）。 */
export type ProjectSection =
  | 'overview'
  | 'foundation'
  | 'planning'
  | 'writing'
  | 'map'
  | 'review'
export type IllustrationKey = 'city' | 'mountains' | 'desk'
export interface IllustrationState { defaults: Record<IllustrationKey, string>; custom: Partial<Record<IllustrationKey, string>> }
