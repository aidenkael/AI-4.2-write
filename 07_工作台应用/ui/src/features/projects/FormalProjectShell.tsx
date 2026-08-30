/**
 * 正式项目外壳：作品页 → 概览 → 正在写 共享的唯一正式 project_id。
 *
 * 职责只限：
 * - 通过后端 `listProjects()` 加载正式作品列表；
 * - 持有 selectedProjectId（正式 project_id），暴露 { project_id, name }；
 * - 打开项目先经 `openProject({project_id})` 后端校验，成功后才提交选择（失败不改选择）；
 * - 暴露 loading / error / reload；
 * - 显式 clearSelection() 仅供明确的"关闭/切换项目"动作使用。
 *
 * 选择是工作台上下文，不是页面挂载状态：全局导航（设置 / 素材与学习 /
 * 灵感箱 / 作品）绝不自动清除正式项目选择；打开另一部正式作品显式替换选择。
 *
 * 明确不引入：通用实体 store / Redux / URL 路由迁移 / 持久化 / 全局工作流引擎。
 * Mock AppStore 身份与本外壳严格分离：生产页面（作品 / ProjectLayout /
 * 全部作品内页面）不得使用 `useActiveProject()` 获取正式身份。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { listProjects, openProject, type ProjectItem } from '../../bridge/client'

export interface FormalProjectSelection {
  project_id: string
  name: string
}

export interface FormalProjectShellValue {
  /** 后端正式作品列表（仅 { project_id, name }，无任何 Mock 字段）。 */
  projects: ProjectItem[]
  /** 当前选中的正式作品（经 openProject 校验提交）。 */
  selected: FormalProjectSelection | null
  loading: boolean
  error: string | null
  reload(): Promise<void>
  /** 校验并打开正式作品：openProject 成功后提交选择；失败保持原选择不变。 */
  openProjectById(projectId: string): Promise<boolean>
  clearSelection(): void
}

export const FormalProjectShellContext = createContext<FormalProjectShellValue | null>(null)

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function FormalProjectShellProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<ProjectItem[]>([])
  const [selected, setSelected] = useState<FormalProjectSelection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await listProjects()
      setProjects(items)
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const openProjectById = useCallback(async (projectId: string): Promise<boolean> => {
    setError(null)
    try {
      const opened = await openProject({ project_id: projectId })
      // 只有后端确认存在并返回正式身份后才提交选择；绝不猜测 / 映射 Mock id
      setSelected({ project_id: opened.project_id, name: opened.name })
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    }
  }, [])

  const clearSelection = useCallback(() => {
    setSelected(null)
  }, [])

  const value = useMemo<FormalProjectShellValue>(
    () => ({ projects, selected, loading, error, reload, openProjectById, clearSelection }),
    [projects, selected, loading, error, reload, openProjectById, clearSelection],
  )

  return <FormalProjectShellContext.Provider value={value}>{children}</FormalProjectShellContext.Provider>
}

export function useFormalProjectShell(): FormalProjectShellValue {
  const value = useContext(FormalProjectShellContext)
  if (!value) throw new Error('useFormalProjectShell must be inside FormalProjectShellProvider')
  return value
}
