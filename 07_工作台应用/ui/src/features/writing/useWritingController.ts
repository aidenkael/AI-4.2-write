/**
 * WritingPage 真实 StoryWrite 消费者控制器。
 *
 * 正式项目身份不再由本控制器持有：projectId 由 FormalProjectShell 传入，
 * WritingPage 不拥有第二个项目选择器。
 *
 * 关键约束：
 * - 候选是后端持有（只读），confirm 只回传 { project_id, writing_token }；
 * - 轮询单一循环、无重叠调用；unmount / 完成 / 失败 / 取消 / 换项目时停止；
 * - projectId 变化（换正式项目）时先取消/丢弃旧请求与候选，绝不把
 *   request_id / writing_token / candidate 带到新项目；
 * - projectId 为空（未选择正式项目）时只回 idle，绝不自动挑选项目。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelStoryWriteRequest,
  confirmStoryWrite,
  getStoryWriteRequest,
  getStoryWriteSurface,
  prepareStoryWrite,
  type ProposeStoryWriteResult,
  type StoryWriteSurface,
} from '../../bridge/client'

export type WritingStatus =
  | 'loading'
  | 'idle'
  | 'running'
  | 'waiting_gowrite'
  | 'waiting_prose_gowrite'
  | 'waiting_confirmation'
  | 'confirming'
  | 'accepted'
  | 'failed'

export type WritingPhase = 'pending_selection' | 'pending_prose' | null

export interface WritingControllerState {
  writingSurface: StoryWriteSurface | null
  selectedChapterNumber: number | null
  authorInput: string
  requestId: string | null
  writingToken: string | null
  candidate: ProposeStoryWriteResult | null
  status: WritingStatus
  /** 交互桥阶段（pending_selection / pending_prose；Direct 为 null）。 */
  phase: WritingPhase
  /** 后端返回的作者可读阶段提示（如“等待 Qoder /gowrite：正在选择本次写作上下文”）。 */
  phaseMessage: string | null
  error: string | null
  /** 后端返回的非机密执行元数据（execution_mode / agent_id / model）。 */
  execution: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
}

export interface WritingController {
  state: WritingControllerState
  selectChapter(chapterNumber: number): void
  setAuthorInput(input: string): void
  generate(): Promise<void>
  cancel(): Promise<void>
  discard(): Promise<void>
  regenerate(): Promise<void>
  confirm(): Promise<void>
}

const POLL_INTERVAL_MS = 700

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useWritingController(options: {
  projectId: string | null
  notify?: (message: string) => void
}): WritingController {
  const { projectId, notify } = options
  const [state, setState] = useState<WritingControllerState>({
    writingSurface: null,
    selectedChapterNumber: null,
    authorInput: '',
    requestId: null,
    writingToken: null,
    candidate: null,
    status: 'idle',
    phase: null,
    phaseMessage: null,
    error: null,
    execution: null,
  })
  const stateRef = useRef(state)
  stateRef.current = state

  // 当前正式项目（异步闭包读最新值；换项目时丢弃在途 surface/轮询结果）
  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId
  // 同步活跃请求指针（避免异步闭包读到过期 state）
  const activeRequestRef = useRef<string | null>(null)
  // 轮询会话：stop 时自增，在途异步结果按会话丢弃（防串/防重叠）
  const pollSessionRef = useRef(0)
  const pollTimerRef = useRef<number | null>(null)

  const set = useCallback((patch: Partial<WritingControllerState>) => {
    setState((current) => ({ ...current, ...patch }))
  }, [])

  const stopPolling = useCallback(() => {
    pollSessionRef.current += 1
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const loadSurface = useCallback(
    async (pid: string) => {
      set({ status: 'loading', error: null })
      try {
        const surface = await getStoryWriteSurface(pid)
        if (projectRef.current !== pid) return // 加载期间已切换项目 → 丢弃过期结果
        set({
          writingSurface: surface,
          selectedChapterNumber: surface.active_chapter_number,
          status: 'idle',
        })
      } catch (e) {
        if (projectRef.current !== pid) return
        set({ error: toMessage(e), status: 'failed' })
      }
    },
    [set],
  )

  // 项目切换 / 挂载协调：先取消/丢弃旧请求与候选，再加载新项目写作面
  useEffect(() => {
    const oldRequestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    set({ requestId: null, writingToken: null, candidate: null, phase: null, phaseMessage: null, error: null, execution: null })
    if (!projectId) {
      set({ writingSurface: null, selectedChapterNumber: null, status: 'idle' })
      return
    }
    let cancelled = false
    void (async () => {
      if (oldRequestId) {
        try {
          await cancelStoryWriteRequest(oldRequestId)
        } catch {
          // 后端清理幂等；本地状态无论如何都已清空
        }
      }
      if (cancelled) return
      await loadSurface(projectId)
    })()
    return () => {
      cancelled = true
      stopPolling()
    }
  }, [projectId, loadSurface, set, stopPolling])

  // 单一轮询循环：setTimeout 链，天然无重叠；stopPolling 清定时器 + 弃在途结果
  const startPolling = useCallback(
    (requestId: string) => {
      stopPolling()
      const session = pollSessionRef.current + 1
      pollSessionRef.current = session

      const tick = async () => {
        if (pollSessionRef.current !== session) return
        try {
          const res = await getStoryWriteRequest(requestId)
          if (pollSessionRef.current !== session) return
          if (res.status === 'pending') {
            // 交互桥阶段：pending_selection（等待第一次 /gowrite）/ pending_prose
            // （等待第二次 /gowrite）；Direct 无 phase 保持 running。
            if (res.phase === 'pending_selection') {
              set({
                status: 'waiting_gowrite',
                phase: 'pending_selection',
                phaseMessage: res.message ?? '等待 Qoder /gowrite：正在选择本次写作上下文',
              })
            } else if (res.phase === 'pending_prose') {
              set({
                status: 'waiting_prose_gowrite',
                phase: 'pending_prose',
                phaseMessage: res.message ?? '上下文已准备好，请再次执行 /gowrite 生成正文',
              })
            } else {
              set({ status: 'running', phase: null, phaseMessage: null })
            }
            pollTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
            return
          }
          stopPolling()
          if (res.status === 'completed') {
            if (!res.result) {
              set({ error: '候选数据无效，请重新生成。', status: 'failed', phase: null, phaseMessage: null })
              return
            }
            const exec = res.result.execution
            set({
              candidate: res.result,
              writingToken: res.result.writing_token,
              status: 'waiting_confirmation',
              phase: null,
              phaseMessage: null,
              execution: {
                execution_mode: typeof exec?.execution_mode === 'string' ? exec.execution_mode : undefined,
                agent_id: typeof exec?.agent_id === 'string' ? exec.agent_id : null,
                model: typeof exec?.model === 'string' ? exec.model : null,
              },
            })
          } else if (res.status === 'canceled') {
            activeRequestRef.current = null
            set({ requestId: null, writingToken: null, candidate: null, status: 'idle', phase: null, phaseMessage: null, error: null, execution: null })
          } else {
            activeRequestRef.current = null
            set({ error: res.error || '任务失败，请重新发起。', status: 'failed', phase: null, phaseMessage: null })
          }
        } catch (e) {
          if (pollSessionRef.current !== session) return
          stopPolling()
          activeRequestRef.current = null
          set({ error: toMessage(e), status: 'failed', phase: null, phaseMessage: null })
        }
      }
      pollTimerRef.current = window.setTimeout(tick, 0)
    },
    [set, stopPolling],
  )

  const setAuthorInput = useCallback(
    (input: string) => {
      set({ authorInput: input, error: null })
    },
    [set],
  )

  const selectChapter = useCallback(
    (chapterNumber: number) => {
      set({ selectedChapterNumber: chapterNumber })
    },
    [set],
  )

  const generate = useCallback(async () => {
    const pid = projectRef.current
    const input = stateRef.current.authorInput.trim()
    if (!pid) {
      set({ error: '请先选择正式作品。', status: 'failed' })
      return
    }
    if (!input) {
      set({ error: '请先写下这一段想写什么。', status: 'failed' })
      return
    }
    if (activeRequestRef.current) {
      set({ error: '已有进行中的任务，请先完成或取消。', status: 'failed' })
      return
    }
    set({ error: null, status: 'running' })
    // 会话令牌：await 期间发生取消/换项目（stopPolling 自增）时，本次发起作废
    const startSession = pollSessionRef.current
    try {
      const prepared = await prepareStoryWrite({ project_id: pid, author_input: input })
      if (pollSessionRef.current !== startSession || projectRef.current !== pid) {
        // 已在等待期间被取消/切换：清理刚创建的请求，绝不启动轮询
        activeRequestRef.current = null
        void cancelStoryWriteRequest(prepared.request_id).catch(() => {})
        return
      }
      activeRequestRef.current = prepared.request_id
      set({
        requestId: prepared.request_id,
        phase: prepared.phase === 'pending_selection' ? 'pending_selection' : null,
        phaseMessage: prepared.execution_mode === 'interactive_bridge'
          ? (prepared.message || '等待 Qoder /gowrite：正在选择本次写作上下文')
          : null,
        status: prepared.execution_mode === 'interactive_bridge' ? 'waiting_gowrite' : 'running',
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
        await cancelStoryWriteRequest(requestId)
      } catch {
        // 取消尽力而为；本地状态清空保证 UI 不卡在 running
      }
    }
    set({ requestId: null, writingToken: null, candidate: null, status: 'idle', phase: null, phaseMessage: null, error: null, execution: null })
  }, [set, stopPolling])

  const discard = useCallback(async () => {
    // “不用了”：未确认候选通过后端生命周期丢弃（cancel 清理工作区 → token 失效）
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try {
        await cancelStoryWriteRequest(requestId)
      } catch {
        // 幂等；本地状态清空
      }
    }
    set({ requestId: null, writingToken: null, candidate: null, status: 'idle', phase: null, phaseMessage: null, error: null, execution: null })
  }, [set, stopPolling])

  const regenerate = useCallback(async () => {
    // “换一种”：先丢弃当前未确认候选（后端清理 + token 失效），再以当前输入重新生成；
    // 绝不同时存在两个有效 writing token。
    const requestId = activeRequestRef.current
    stopPolling()
    activeRequestRef.current = null
    if (requestId) {
      try {
        await cancelStoryWriteRequest(requestId)
      } catch {
        // 幂等；继续生成
      }
    }
    set({ requestId: null, writingToken: null, candidate: null, phase: null, phaseMessage: null, error: null, execution: null })
    await generate()
  }, [generate, set, stopPolling])

  const confirm = useCallback(async () => {
    const pid = projectRef.current
    const token = stateRef.current.writingToken
    if (!pid || !token) {
      set({ error: '缺少确认信息，请重新生成。', status: 'failed' })
      return
    }
    set({ status: 'confirming', error: null })
    try {
      const confirmed = await confirmStoryWrite({ project_id: pid, writing_token: token })
      activeRequestRef.current = null
      set({ requestId: null, writingToken: null, candidate: null, phase: null, phaseMessage: null, execution: null })
      // 以正式项目为真相：确认后重新加载写作面
      await loadSurface(pid)
      if (confirmed.chapter_number != null) {
        set({ selectedChapterNumber: confirmed.chapter_number, status: 'accepted' })
      } else {
        set({ status: 'accepted' })
      }
      notify?.('这段已经保留下来了。')
    } catch (e) {
      // 确认失败：保留候选可见，展示真实后端错误，不修改已采用正文面
      set({ error: toMessage(e), status: 'waiting_confirmation' })
    }
  }, [loadSurface, notify, set])

  return {
    state,
    selectChapter,
    setAuthorInput,
    generate,
    cancel,
    discard,
    regenerate,
    confirm,
  }
}
