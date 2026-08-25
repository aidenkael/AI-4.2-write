/**
 * Story Development 真实 StoryPlan 消费者控制器。
 *
 * 正式项目身份由 FormalProjectShell 传入（projectId），本控制器不持有项目选择。
 * 只负责：正式概览读取（getProjectOverview）、作者问题、prepare/轮询/取消/丢弃/
 * 确认/重试，以及后端持有的单个非 canonical 规划候选的展示状态。
 *
 * 关键约束：
 * - 候选是后端返回的单个候选 { proposal, planning_items[] }，只读，绝不伪造多选项；
 * - confirm 只回传 { project_id, planning_token }，不传任何前端构造内容；
 * - 轮询单一循环、无重叠；unmount / 终态 / 换项目时停止；
 * - 换项目先取消/丢弃旧请求与候选，request_id / planning_token / candidate
 *   绝不跨项目携带；
 * - 不包含 Agent / 模型选择（执行配置归 Settings，后端决定执行模式）。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelStoryPlanRequest,
  confirmStoryPlan,
  getProjectOverview,
  getStoryPlanRequest,
  prepareStoryPlan,
  type ProjectOverview,
  type StoryPlanCandidate,
} from '../../bridge/client'

export type DevelopmentStatus =
  | 'loading'
  | 'idle'
  | 'running'
  | 'waiting_confirmation'
  | 'confirming'
  | 'accepted'
  | 'failed'

export interface DevelopmentControllerState {
  overview: ProjectOverview | null
  overviewLoading: boolean
  overviewError: string | null
  authorQuestion: string
  requestId: string | null
  planningToken: string | null
  candidate: StoryPlanCandidate | null
  backendMessage: string | null
  status: DevelopmentStatus
  error: string | null
  /** 后端返回的非机密执行元数据（execution_mode / agent_id / model）。 */
  execution: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
}

export interface DevelopmentController {
  state: DevelopmentControllerState
  setAuthorQuestion(input: string): void
  generate(): Promise<void>
  cancel(): Promise<void>
  discard(): Promise<void>
  regenerate(): Promise<void>
  confirm(): Promise<void>
  reloadOverview(): Promise<void>
}

const POLL_INTERVAL_MS = 700

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useDevelopmentController(options: {
  projectId: string | null
  notify?: (message: string) => void
}): DevelopmentController {
  const { projectId, notify } = options
  const [state, setState] = useState<DevelopmentControllerState>({
    overview: null,
    overviewLoading: true,
    overviewError: null,
    authorQuestion: '',
    requestId: null,
    planningToken: null,
    candidate: null,
    backendMessage: null,
    status: 'idle',
    error: null,
    execution: null,
  })
  const stateRef = useRef(state)
  stateRef.current = state

  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId
  const activeRequestRef = useRef<string | null>(null)
  const pollSessionRef = useRef(0)
  const pollTimerRef = useRef<number | null>(null)

  const set = useCallback((patch: Partial<DevelopmentControllerState>) => {
    setState((current) => ({ ...current, ...patch }))
  }, [])

  const stopPolling = useCallback(() => {
    pollSessionRef.current += 1
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const loadOverview = useCallback(
    async (pid: string) => {
      set({ overviewLoading: true, overviewError: null })
      try {
        const overview = await getProjectOverview(pid)
        if (projectRef.current !== pid) return // 加载期间已切换项目 → 丢弃过期结果
        set({ overview })
      } catch (e) {
        if (projectRef.current !== pid) return
        set({ overviewError: toMessage(e) })
      } finally {
        if (projectRef.current === pid) set({ overviewLoading: false })
      }
    },
    [set],
  )

  // 项目切换 / 挂载协调：先取消/丢弃旧请求与候选，再加载新项目正式概览
  useEffect(() => {
    const oldRequestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    set({ requestId: null, planningToken: null, candidate: null, backendMessage: null, error: null, execution: null })
    if (!projectId) {
      set({ overview: null, overviewLoading: false, status: 'idle' })
      return
    }
    let cancelled = false
    void (async () => {
      if (oldRequestId) {
        try {
          await cancelStoryPlanRequest(oldRequestId)
        } catch {
          // 后端清理幂等；本地状态无论如何都已清空
        }
      }
      if (cancelled) return
      await loadOverview(projectId)
      if (!cancelled) set({ status: 'idle' })
    })()
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [projectId, loadOverview, set, stopPolling])

  const startPolling = useCallback(
    (requestId: string) => {
      stopPolling()
      const session = pollSessionRef.current + 1
      pollSessionRef.current = session

      const tick = async () => {
        if (pollSessionRef.current !== session) return
        try {
          const res = await getStoryPlanRequest(requestId)
          if (pollSessionRef.current !== session) return
          if (res.status === 'pending') {
            // Interactive：等待 /gowrite；Direct：后台执行中。继续轮询
            pollTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
            return
          }
          stopPolling()
          if (res.status === 'completed') {
            if (!res.result) {
              set({ error: '候选数据无效，请重新发起。', status: 'failed' })
              return
            }
            const exec = res.result.execution
            set({
              candidate: res.result.candidate,
              planningToken: res.result.planning_token,
              backendMessage: res.result.message,
              status: 'waiting_confirmation',
              execution: {
                execution_mode: typeof exec?.execution_mode === 'string' ? exec.execution_mode : undefined,
                agent_id: typeof exec?.agent_id === 'string' ? exec.agent_id : null,
                model: typeof exec?.model === 'string' ? exec.model : null,
              },
            })
          } else if (res.status === 'canceled') {
            activeRequestRef.current = null
            set({
              requestId: null,
              planningToken: null,
              candidate: null,
              backendMessage: null,
              status: 'idle',
              error: null,
              execution: null,
            })
          } else {
            activeRequestRef.current = null
            set({ error: res.error || '任务失败，请重新发起。', status: 'failed' })
          }
        } catch (e) {
          if (pollSessionRef.current !== session) return
          stopPolling()
          activeRequestRef.current = null
          set({ error: toMessage(e), status: 'failed' })
        }
      }
      pollTimerRef.current = window.setTimeout(tick, 0)
    },
    [set, stopPolling],
  )

  const setAuthorQuestion = useCallback(
    (input: string) => {
      set({ authorQuestion: input, error: null })
    },
    [set],
  )

  const generate = useCallback(async () => {
    const pid = projectRef.current
    const question = stateRef.current.authorQuestion.trim()
    if (!pid) {
      set({ error: '请先选择正式作品。', status: 'failed' })
      return
    }
    if (!question) {
      set({ error: '请先写下你想一起想的问题。', status: 'failed' })
      return
    }
    if (activeRequestRef.current) {
      set({ error: '已有进行中的规划任务，请先完成或取消。', status: 'failed' })
      return
    }
    set({ error: null, status: 'running' })
    // 会话令牌：await 期间发生取消/换项目（stopPolling 自增）时，本次发起作废
    const startSession = pollSessionRef.current
    try {
      const prepared = await prepareStoryPlan({ project_id: pid, author_question: question })
      if (pollSessionRef.current !== startSession || projectRef.current !== pid) {
        // 已在等待期间被取消/切换：清理刚创建的请求，绝不启动轮询
        activeRequestRef.current = null
        void cancelStoryPlanRequest(prepared.request_id).catch(() => {})
        return
      }
      activeRequestRef.current = prepared.request_id
      set({
        requestId: prepared.request_id,
        backendMessage: prepared.message,
        execution: {
          execution_mode: prepared.execution_mode,
          agent_id: prepared.agent_id ?? null,
          model: prepared.model ?? null,
        },
      })
      startPolling(prepared.request_id)
    } catch (e) {
      if (pollSessionRef.current === startSession) {
        activeRequestRef.current = null
        set({ error: toMessage(e), status: 'failed' })
      }
    }
  }, [set, startPolling])

  const cancel = useCallback(async () => {
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try {
        await cancelStoryPlanRequest(requestId)
      } catch {
        // 取消尽力而为；本地状态清空保证 UI 不卡在 running
      }
    }
    set({
      requestId: null,
      planningToken: null,
      candidate: null,
      backendMessage: null,
      status: 'idle',
      error: null,
    })
  }, [set, stopPolling])

  const discard = useCallback(async () => {
    // “暂时不决定”：未确认候选通过后端生命周期丢弃（cancel 清理工作区 → token 失效）
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try {
        await cancelStoryPlanRequest(requestId)
      } catch {
        // 幂等；本地状态清空
      }
    }
    set({
      requestId: null,
      planningToken: null,
      candidate: null,
      backendMessage: null,
      status: 'idle',
      error: null,
    })
  }, [set, stopPolling])

  const regenerate = useCallback(async () => {
    // “换一个建议”：先丢弃当前未确认候选（后端清理 + token 失效），
    // 再以当前问题重新生成；绝不同时存在两个有效 planning token。
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try {
        await cancelStoryPlanRequest(requestId)
      } catch {
        // 幂等；继续生成
      }
    }
    set({ requestId: null, planningToken: null, candidate: null, backendMessage: null, error: null })
    await generate()
  }, [generate, set, stopPolling])

  const confirm = useCallback(async () => {
    const pid = projectRef.current
    const token = stateRef.current.planningToken
    if (!pid || !token) {
      set({ error: '缺少确认信息，请重新发起。', status: 'failed' })
      return
    }
    set({ status: 'confirming', error: null })
    try {
      const confirmed = await confirmStoryPlan({ project_id: pid, planning_token: token })
      activeRequestRef.current = null
      set({ requestId: null, planningToken: null, candidate: null, backendMessage: null })
      // 以正式项目为真相：确认后重载正式概览（current_plans 反映新写入的规划）
      await loadOverview(pid)
      set({ status: 'accepted' })
      notify?.(confirmed.message || '规划已确认并写入。')
    } catch (e) {
      // 确认失败：保留候选可见，展示真实后端错误，不修改已确认规划展示
      set({ error: toMessage(e), status: 'waiting_confirmation' })
    }
  }, [loadOverview, notify, set])

  const reloadOverview = useCallback(async () => {
    const pid = projectRef.current
    if (!pid) return
    await loadOverview(pid)
  }, [loadOverview])

  return {
    state,
    setAuthorQuestion,
    generate,
    cancel,
    discard,
    regenerate,
    confirm,
    reloadOverview,
  }
}
