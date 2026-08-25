/**
 * 作品检查真实 scoped AI 消费者控制器。
 *
 * 约束：
 * - 页面加载只读（getReviewSurface），零模型；
 * - 只有作者显式"开始检查"才发起一次 Agent 检查（默认最新已接受章节）；
 * - 报告非权威、零写回；cancel/late-result 安全；换项目丢弃过期状态。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelReviewRequest,
  getReviewRequest,
  getReviewSurface,
  prepareReview,
  type ReviewReport,
  type ReviewSurface,
} from '../../bridge/client'

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

const POLL_INTERVAL_MS = 700
const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useReviewController(projectId: string | null): ReviewController {
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
  const activeRequestRef = useRef<string | null>(null)
  const pollSessionRef = useRef(0)
  const pollTimerRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    pollSessionRef.current += 1
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

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
    const oldRequestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
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
    void (async () => {
      if (oldRequestId) {
        try { await cancelReviewRequest(oldRequestId) } catch { /* 幂等 */ }
      }
      await loadSurface(projectId)
    })()
    return () => {
      // 卸载（切页面/全局导航）时除了停止本地轮询，还要取消仍在后台运行的
      // Direct 检查，避免占用单活跃执行槽、避免报告迟到写回已离开的页面。
      stopPolling()
      const pending = activeRequestRef.current
      if (pending) {
        activeRequestRef.current = null
        void cancelReviewRequest(pending).catch(() => {})
      }
    }
  }, [projectId, loadSurface, stopPolling])

  const selectChapter = useCallback((chapterNumber: number) => {
    setSelectedChapter(chapterNumber)
    setReport(null)
  }, [])

  const reloadSurface = useCallback(async () => {
    if (projectId) await loadSurface(projectId)
  }, [loadSurface, projectId])

  const start = useCallback(async () => {
    const pid = projectRef.current
    if (!pid) { setError('请先选择正式作品。'); setStatus('failed'); return }
    if (activeRequestRef.current) { setError('已有进行中的检查，请先完成或取消。'); setStatus('failed'); return }
    setError(null)
    setStatus('running')
    // 会话令牌：await 期间发生取消/换项目（stopPolling 自增）时，本次发起作废，
    // 避免"取消后 prepare 才返回"导致检查继续跑并串到新页面/新项目。
    const startSession = pollSessionRef.current
    try {
      const prepared = await prepareReview({ project_id: pid, chapter_number: selectedChapter ?? undefined })
      if (pollSessionRef.current !== startSession || projectRef.current !== pid) {
        // 已在等待期间被取消/切换：清理刚创建的请求，绝不启动轮询
        activeRequestRef.current = null
        void cancelReviewRequest(prepared.request_id).catch(() => {})
        return
      }
      activeRequestRef.current = prepared.request_id
      setExecution({
        execution_mode: prepared.execution_mode,
        agent_id: prepared.agent_id ?? null,
        model: prepared.model ?? null,
      })
      const session = pollSessionRef.current + 1
      pollSessionRef.current = session
      const tick = async () => {
        if (pollSessionRef.current !== session) return
        try {
          const res = await getReviewRequest(prepared.request_id)
          if (pollSessionRef.current !== session) return
          if (res.status === 'pending') {
            pollTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
            return
          }
          stopPolling()
          activeRequestRef.current = null
          if (res.status === 'completed' && res.result) {
            const exec = res.result.execution
            setExecution({
              execution_mode: typeof exec?.execution_mode === 'string' ? exec.execution_mode : undefined,
              agent_id: typeof exec?.agent_id === 'string' ? exec.agent_id : null,
              model: typeof exec?.model === 'string' ? exec.model : null,
            })
            setReport(res.result)
            setStatus('completed')
          } else if (res.status === 'canceled') {
            setExecution(null)
            setStatus('idle')
          } else {
            setExecution(null)
            setError(res.error || '检查失败，请重试。')
            setStatus('failed')
          }
        } catch (e) {
          if (pollSessionRef.current !== session) return
          stopPolling()
          activeRequestRef.current = null
          setExecution(null)
          setError(toMessage(e))
          setStatus('failed')
        }
      }
      pollTimerRef.current = window.setTimeout(tick, 0)
    } catch (e) {
      if (pollSessionRef.current === startSession) {
        activeRequestRef.current = null
        setExecution(null)
        setError(toMessage(e))
        setStatus('failed')
      }
    }
  }, [selectedChapter, stopPolling])

  const cancel = useCallback(async () => {
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try { await cancelReviewRequest(requestId) } catch { /* 幂等 */ }
    }
    setReport(null)
    setExecution(null)
    setStatus('idle')
    setError(null)
  }, [stopPolling])

  return {
    surface, surfaceLoading, surfaceError, report, status, error, selectedChapter, execution,
    selectChapter, reloadSurface, start, cancel,
  }
}
