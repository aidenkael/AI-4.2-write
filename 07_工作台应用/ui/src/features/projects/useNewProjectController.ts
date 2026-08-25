/**
 * 新建作品真实 StoryDesign 消费者控制器。
 *
 * 关键约束：
 * - 候选是后端返回的单个候选（proposal / work_direction / reader_promise /
 *   hard_constraints / open_space / unknowns），只读，绝不伪造多方向；
 * - confirm 只回传 { proposal_token }，不传任何前端构造内容；
 * - 轮询单一循环、无重叠；cancel/discard 走后端生命周期清理，token 失效；
 * - 执行模式由 Settings 决定（Direct 后台执行 / Interactive /gowrite），UI 不分支。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelNewProjectRequest,
  confirmNewProject,
  getNewProjectRequest,
  prepareNewProject,
  type ConfirmResult,
  type StoryCandidate,
} from '../../bridge/client'

export type NewProjectStatus =
  | 'idle'
  | 'running'
  | 'waiting_confirmation'
  | 'confirming'
  | 'accepted'
  | 'failed'

export interface NewProjectControllerState {
  name: string
  idea: string
  requestId: string | null
  proposalToken: string | null
  candidate: StoryCandidate | null
  backendMessage: string | null
  status: NewProjectStatus
  error: string | null
  confirmed: ConfirmResult | null
  /** 后端返回的非机密执行元数据（execution_mode / agent_id / model）。 */
  execution: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
}

export interface NewProjectController {
  state: NewProjectControllerState
  setName(input: string): void
  setIdea(input: string): void
  generate(): Promise<void>
  cancel(): Promise<void>
  discard(): Promise<void>
  regenerate(): Promise<void>
  /** 确认并创建正式作品；成功返回后端确认结果，失败返回 null（error 已写入 state）。 */
  confirm(): Promise<ConfirmResult | null>
  reset(): void
}

const POLL_INTERVAL_MS = 700

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useNewProjectController(options: { notify?: (message: string) => void }): NewProjectController {
  const { notify } = options
  const [state, setState] = useState<NewProjectControllerState>({
    name: '',
    idea: '',
    requestId: null,
    proposalToken: null,
    candidate: null,
    backendMessage: null,
    status: 'idle',
    error: null,
    confirmed: null,
    execution: null,
  })
  const stateRef = useRef(state)
  stateRef.current = state

  const activeRequestRef = useRef<string | null>(null)
  const pollSessionRef = useRef(0)
  const pollTimerRef = useRef<number | null>(null)

  const set = useCallback((patch: Partial<NewProjectControllerState>) => {
    setState((current) => ({ ...current, ...patch }))
  }, [])

  const stopPolling = useCallback(() => {
    pollSessionRef.current += 1
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  // 卸载时停止轮询并尽力清理在途请求
  useEffect(() => {
    return () => {
      stopPolling()
      const rid = activeRequestRef.current
      if (rid) void cancelNewProjectRequest(rid).catch(() => {})
    }
  }, [stopPolling])

  const startPolling = useCallback(
    (requestId: string) => {
      stopPolling()
      const session = pollSessionRef.current + 1
      pollSessionRef.current = session
      const tick = async () => {
        if (pollSessionRef.current !== session) return
        try {
          const res = await getNewProjectRequest(requestId)
          if (pollSessionRef.current !== session) return
          if (res.status === 'pending') {
            pollTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
            return
          }
          stopPolling()
          if (res.status === 'completed') {
            if (!res.result) {
              set({ error: '候选数据无效，请重新生成。', status: 'failed' })
              return
            }
            const exec = res.result.execution
            set({
              candidate: res.result.candidate,
              proposalToken: res.result.proposal_token,
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
            set({ requestId: null, proposalToken: null, candidate: null, backendMessage: null, status: 'idle', error: null, execution: null })
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

  const setName = useCallback((input: string) => set({ name: input, error: null }), [set])
  const setIdea = useCallback((input: string) => set({ idea: input, error: null }), [set])

  const generate = useCallback(async () => {
    const name = stateRef.current.name.trim()
    const idea = stateRef.current.idea.trim()
    if (!name) { set({ error: '请填写作品名。', status: 'failed' }); return }
    if (!idea) { set({ error: '请写下你的想法。', status: 'failed' }); return }
    if (activeRequestRef.current) { set({ error: '已有进行中的任务，请先完成或取消。', status: 'failed' }); return }
    set({ error: null, status: 'running' })
    try {
      const prepared = await prepareNewProject({ name, idea })
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
      activeRequestRef.current = null
      set({ error: toMessage(e), status: 'failed' })
    }
  }, [set, startPolling])

  const cancel = useCallback(async () => {
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try { await cancelNewProjectRequest(requestId) } catch { /* 幂等 */ }
    }
    set({ requestId: null, proposalToken: null, candidate: null, backendMessage: null, status: 'idle', error: null, execution: null })
  }, [set, stopPolling])

  const discard = useCallback(async () => {
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try { await cancelNewProjectRequest(requestId) } catch { /* 幂等 */ }
    }
    set({ requestId: null, proposalToken: null, candidate: null, backendMessage: null, status: 'idle', error: null, execution: null })
  }, [set, stopPolling])

  const regenerate = useCallback(async () => {
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try { await cancelNewProjectRequest(requestId) } catch { /* 幂等 */ }
    }
    set({ requestId: null, proposalToken: null, candidate: null, backendMessage: null, error: null, execution: null })
    await generate()
  }, [generate, set, stopPolling])

  const confirm = useCallback(async (): Promise<ConfirmResult | null> => {
    const token = stateRef.current.proposalToken
    if (!token) { set({ error: '缺少确认信息，请重新生成。', status: 'failed' }); return null }
    set({ status: 'confirming', error: null })
    try {
      const confirmed = await confirmNewProject({ proposal_token: token })
      activeRequestRef.current = null
      set({ requestId: null, proposalToken: null, candidate: null, backendMessage: null, confirmed, status: 'accepted' })
      notify?.(confirmed.message || '作品已创建')
      return confirmed
    } catch (e) {
      set({ error: toMessage(e), status: 'waiting_confirmation' })
      return null
    }
  }, [notify, set])

  const reset = useCallback(() => {
    stopPolling()
    activeRequestRef.current = null
    set({
      name: '', idea: '', requestId: null, proposalToken: null, candidate: null,
      backendMessage: null, status: 'idle', error: null, confirmed: null, execution: null,
    })
  }, [set, stopPolling])

  return { state, setName, setIdea, generate, cancel, discard, regenerate, confirm, reset }
}
