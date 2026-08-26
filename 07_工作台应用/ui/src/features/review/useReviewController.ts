/**
 * 作品检查真实 scoped AI 消费者控制器（App 级协调器消费者）。
 *
 * 根不变量：AI 任务属于 Go Write（AuthorTaskCoordinator），不属于页面。
 * 离开 Review 页任务继续运行、报告保留；返回后页面显式消费报告。
 *
 * 约束：
 * - 页面加载只读（getReviewSurface），零模型；
 * - 只有作者显式"开始检查"才发起一次 Agent 检查；
 * - 报告非权威、零写回；cancel/late-result 安全；换项目丢弃过期状态。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getReviewSurface,
  type ReviewReport,
  type ReviewSurface,
} from '../../bridge/client'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'

export type ReviewStatus =
  | 'loading'
  | 'idle'
  | 'running'
  | 'completed'
  | 'failed'

export interface ReviewController {
  surface: ReviewSurface | null
  surfaceLoading: boolean
  surfaceError: string | null
  report: ReviewReport | null
  status: ReviewStatus
  error: string | null
  selectedChapter: number | null
  /** 后端返回的非机密执行元数据（execution_mode / agent_id / model）。 */
  execution: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
  selectChapter(chapterNumber: number): void
  reloadSurface(): Promise<void>
  start(): Promise<void>
  cancel(): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useReviewController(projectId: string | null): ReviewController {
  const { task, start: startTask, cancel: cancelTask, consume } = useAuthorTask()
  const [surface, setSurface] = useState<ReviewSurface | null>(null)
  const [surfaceLoading, setSurfaceLoading] = useState(true)
  const [surfaceError, setSurfaceError] = useState<string | null>(null)
  const [report, setReport] = useState<ReviewReport | null>(null)
  const [status, setStatus] = useState<ReviewStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [execution, setExecution] = useState<ReviewController['execution']>(null)

  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId

  const loadSurface = useCallback(async (pid: string) => {
    setSurfaceLoading(true)
    setSurfaceError(null)
    try {
      const next = await getReviewSurface(pid)
      if (projectRef.current !== pid) return
      setSurface(next)
      setSelectedChapter((current) => current ?? next.latest_chapter_number)
    } catch (e) {
      if (projectRef.current !== pid) return
      setSurfaceError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setSurfaceLoading(false)
    }
  }, [])

  useEffect(() => {
    setReport(null)
    setStatus('idle')
    setError(null)
    setExecution(null)
    setSelectedChapter(null)
    if (!projectId) {
      setSurface(null)
      setSurfaceLoading(false)
      return
    }
    void loadSurface(projectId)
  }, [projectId, loadSurface])

  // 协调器任务 → 本页：运行中直接映射；候选/失败由页面显式消费（adopt + consume）。
  const taskMatches = task?.kind === 'review' && (!projectId || !task.projectId || task.projectId === projectId)

  useEffect(() => {
    if (!taskMatches) return
    if (task.status === 'running' || task.status === 'waiting_author') {
      setStatus('running')
      setError(null)
      setExecution(task.execution
        ? {
            execution_mode: task.execution.execution_mode ?? undefined,
            agent_id: task.execution.agent_id ?? null,
            model: task.execution.model ?? null,
          }
        : null)
      return
    }
    if (task.status === 'candidate' && task.result) {
      // 显式消费：报告 adopt 到本页展示后，协调器任务清除（不再占全局任务条）
      const result = task.result as ReviewReport
      setReport(result)
      setStatus('completed')
      setExecution(result.execution
        ? {
            execution_mode: typeof result.execution?.execution_mode === 'string' ? result.execution.execution_mode : undefined,
            agent_id: typeof result.execution?.agent_id === 'string' ? result.execution.agent_id : null,
            model: typeof result.execution?.model === 'string' ? result.execution.model : null,
          }
        : null)
      setError(null)
      consume()
      return
    }
    if (task.status === 'failed') {
      setReport(null)
      setStatus('failed')
      setError(task.error ?? '检查失败，请重试。')
      setExecution(null)
      consume()
      return
    }
  }, [task, taskMatches, consume])

  const selectChapter = useCallback((chapterNumber: number) => {
    setSelectedChapter(chapterNumber)
    setReport(null)
    setStatus('idle')
  }, [])

  const reloadSurface = useCallback(async () => {
    if (projectId) await loadSurface(projectId)
  }, [loadSurface, projectId])

  const start = useCallback(async () => {
    const pid = projectRef.current
    if (!pid) { setError('请先选择正式作品。'); setStatus('failed'); return }
    setReport(null)
    setStatus('running')
    setError(null)
    const busy = await startTask({ kind: 'review', project_id: pid, chapter_number: selectedChapter ?? undefined })
    if (busy) {
      setStatus('failed')
      setError(busy)
    }
  }, [selectedChapter, startTask])

  const cancel = useCallback(async () => {
    setReport(null)
    setExecution(null)
    setStatus('idle')
    setError(null)
    await cancelTask()
  }, [cancelTask])

  return {
    surface, surfaceLoading, surfaceError, report, status, error, selectedChapter, execution,
    selectChapter, reloadSurface, start, cancel,
  }
}
