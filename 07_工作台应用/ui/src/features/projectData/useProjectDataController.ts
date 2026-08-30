/**
 * 作品地基 / 故事地图 只读正式 Story State 投影消费者控制器（共用）。
 *
 * 约束：只读 getProjectData；零写回、零模型；换项目丢弃过期结果。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { getProjectData, type ProjectData } from '../../bridge/client'

export interface ProjectDataController {
  data: ProjectData | null
  loading: boolean
  error: string | null
  reload(): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useProjectDataController(projectId: string | null): ProjectDataController {
  const [data, setData] = useState<ProjectData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId

  const load = useCallback(async (pid: string) => {
    setLoading(true)
    setError(null)
    try {
      const next = await getProjectData(pid)
      if (projectRef.current !== pid) return
      setData(next)
    } catch (e) {
      if (projectRef.current !== pid) return
      setError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!projectId) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    void load(projectId)
  }, [projectId, load])

  const reload = useCallback(async () => {
    if (projectId) await load(projectId)
  }, [load, projectId])

  return { data, loading, error, reload }
}
