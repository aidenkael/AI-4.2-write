/**
 * 新建作品真实 StoryDesign 消费者控制器（App 级协调器消费者）。
 *
 * 根不变量：AI 任务属于 Go Write（AuthorTaskCoordinator），不属于页面。
 * 关闭对话框/离开 Projects 页，任务继续推进、候选保留；返回后自动附着。
 *
 * 关键约束：
 * - 候选是后端返回的单个候选，只读，绝不伪造多方向；
 * - confirm 只回传 { proposal_token }，不传任何前端构造内容；
 * - 执行模式由 Settings 决定（Direct 后台执行 / Interactive /gowrite），UI 不分支。
 */
import { useCallback, useRef, useState } from 'react'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'
import type { ConfirmResult, StoryCandidate } from '../../bridge/client'

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

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

function taskView(
  task: ReturnType<typeof useAuthorTask>['task'],
): Pick<NewProjectControllerState, 'requestId' | 'proposalToken' | 'candidate' | 'backendMessage' | 'status' | 'error' | 'execution'> | null {
  if (!task || task.kind !== 'new_project') return null
  const base = {
    requestId: task.requestId || null,
    proposalToken: null as string | null,
    candidate: null as StoryCandidate | null,
    backendMessage: task.message,
    error: task.error,
    execution: task.execution
      ? {
          execution_mode: task.execution.execution_mode ?? undefined,
          agent_id: task.execution.agent_id ?? null,
          model: task.execution.model ?? null,
        }
      : null,
  }
  switch (task.status) {
    case 'running':
    case 'waiting_author':
      return { ...base, status: 'running' }
    case 'candidate': {
      const result = task.result as { proposal_token?: string; candidate?: StoryCandidate; message?: string } | null
      return {
        ...base,
        status: 'waiting_confirmation',
        proposalToken: result?.proposal_token ?? null,
        candidate: result?.candidate ?? null,
        backendMessage: result?.message ?? task.message,
      }
    }
    case 'confirming':
      return { ...base, status: 'confirming' }
    case 'failed':
      return { ...base, status: 'failed' }
    default:
      return null
  }
}

export function useNewProjectController(options: { notify?: (message: string) => void }): NewProjectController {
  const { notify } = options
  const { task, start, cancel: cancelTask, confirm: confirmTask } = useAuthorTask()
  const [name, setNameState] = useState('')
  const [idea, setIdeaState] = useState('')
  const [confirmed, setConfirmed] = useState<ConfirmResult | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  const nameRef = useRef(name)
  nameRef.current = name
  const ideaRef = useRef(idea)
  ideaRef.current = idea

  const view = taskView(task)
  const candidate = view?.candidate ?? null

  const state: NewProjectControllerState = {
    name,
    idea,
    requestId: view?.requestId ?? null,
    proposalToken: view?.proposalToken ?? null,
    candidate,
    backendMessage: view?.backendMessage ?? null,
    status: view?.status ?? (confirmed ? 'accepted' : 'idle'),
    error: view?.error ?? localError,
    confirmed,
    execution: view?.execution ?? null,
  }

  const setName = useCallback((input: string) => {
    setNameState(input)
    setLocalError(null)
  }, [])

  const setIdea = useCallback((input: string) => {
    setIdeaState(input)
    setLocalError(null)
  }, [])

  const generate = useCallback(async () => {
    const n = nameRef.current.trim()
    const i = ideaRef.current.trim()
    if (!n) { setLocalError('请填写作品名。'); return }
    if (!i) { setLocalError('请写下你的想法。'); return }
    setConfirmed(null)
    const busy = await start({ kind: 'new_project', name: n, idea: i })
    if (busy) setLocalError(busy)
  }, [start])

  const cancel = useCallback(async () => {
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const discard = useCallback(async () => {
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const regenerate = useCallback(async () => {
    setLocalError(null)
    await cancelTask()
    await generate()
  }, [cancelTask, generate])

  const confirm = useCallback(async (): Promise<ConfirmResult | null> => {
    try {
      const result = await confirmTask('new_project')
      if (!result) {
        setLocalError(task?.error ?? '确认失败，请重试。')
        return null
      }
      const confirmedResult = result as ConfirmResult
      setConfirmed(confirmedResult)
      notify?.(confirmedResult.message || '作品已创建')
      return confirmedResult
    } catch (e) {
      setLocalError(toMessage(e))
      return null
    }
  }, [confirmTask, notify, task?.error])

  const reset = useCallback(() => {
    setNameState('')
    setIdeaState('')
    setConfirmed(null)
    setLocalError(null)
  }, [])

  return { state, setName, setIdea, generate, cancel, discard, regenerate, confirm, reset }
}
