/**
 * App 级 Author Task Coordinator：唯一拥有作者 AI 操作 UI 生命周期的组件。
 *
 * 根不变量：AI 任务属于 Go Write，不属于挂载的页面组件。本组件挂在 Router
 * 之上（App.tsx），页面切换/卸载绝不影响任务的推进、结果保留与项目身份。
 *
 * 职责（保持窄，不是工作流引擎/事件总线）：
 * - 持有唯一活跃作者操作：kind / request_id / project_id / status / phase /
 *   author-readable message / 非机密执行元数据 / 结果（候选/报告/计划）/
 *   error / 目标页面；
 * - 单一轮询会话（setTimeout 链，无重叠）；页面卸载后继续轮询，后端阶段
 *   推进不依赖任何页面挂载；
 * - 阶段要求作者动作时通知一次、完成/失败时通知一次（绝不伪造进度）；
 * - 结果保留到作者确认/丢弃/页面显式消费；
 * - 取消/确认/丢弃/重试是唯一权威动作；跨项目校验由后端强制。
 * - remount/reload 后通过 get_active_author_operation() 恢复待办操作。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  cancelMaterialClassifyRequest,
  cancelMaterialDistillRequest,
  cancelNewProjectRequest,
  cancelReviewRequest,
  cancelStoryPlanRequest,
  cancelStoryWriteRequest,
  classifyMaterialInbox,
  confirmNewProject,
  confirmStoryPlan,
  confirmStoryWrite,
  getActiveAuthorOperation,
  getMaterialClassifyRequest,
  getMaterialDistillRequest,
  getNewProjectRequest,
  getReviewRequest,
  getStoryPlanRequest,
  getStoryWriteRequest,
  prepareNewProject,
  prepareReview,
  prepareStoryPlan,
  prepareStoryWrite,
  distillMaterial,
  type BookDistillRequestStatus,
  type ClassifyRequestStatus,
  type ConfirmResult,
  type ConfirmStoryPlanResult,
  type ConfirmStoryWriteResult,
  type NewProjectRequestStatus,
  type ProposeResult,
  type ProposeStoryPlanResult,
  type ProposeStoryWriteResult,
  type ReviewReport,
  type ReviewRequestStatus,
  type StoryPlanRequestStatus,
  type StoryWriteRequestStatus,
} from '../../bridge/client'
import { useApp } from '../app/AppStore'
import { playCompletionSound } from './sound'
import {
  candidateReadyMessage,
  deriveTaskStatus,
  isTaskActive,
  taskTarget,
  waitingAuthorMessage,
  type AuthorTask,
  type AuthorTaskKind,
} from './taskModel'

const POLL_INTERVAL_MS = 700

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** 各操作 prepare 的 payload（页面本地输入不属于任务状态）。 */
export type TaskPayload =
  | { kind: 'new_project'; name: string; idea: string }
  | { kind: 'story_plan'; project_id: string; author_question: string }
  | { kind: 'story_write'; project_id: string; author_input: string; chapter_number?: number }
  | { kind: 'review'; project_id: string; chapter_number?: number }
  | { kind: 'material_classify' }
  | { kind: 'material_distill'; asset_id: string }

export interface AuthorTaskController {
  /** 当前任务（无任务为 null；failed 保留到页面消费或重试）。 */
  task: AuthorTask | null
  /** 启动操作；已有活跃任务时返回作者可读错误（不覆盖）。 */
  start(payload: TaskPayload): Promise<string | null>
  /** 显式取消（运行中/等待中）；候选丢弃同样走这里。 */
  cancel(): Promise<void>
  /** 作者明确确认（new_project / story_plan / story_write）；成功后任务清除。 */
  confirm(kind: 'new_project' | 'story_plan' | 'story_write'): Promise<unknown | null>
  /** 页面显式消费结果（review 报告 / 素材计划 / 蒸馏完成 / 失败展示后清理）。 */
  consume(): void
  /** 返回任务所属页面/区块（保持正式项目选择）。 */
  navigateToTask(): void
  /** remount/reload 后恢复后端仍存在的待办操作（幂等，只执行一次）。 */
  resume(): Promise<void>
}

export const AuthorTaskContext = createContext<AuthorTaskController | null>(null)

type PollStatus = { status: string; phase?: string | null; message?: string | null; result?: unknown | null; error?: string | null }

const pollers: Record<AuthorTaskKind, (requestId: string) => Promise<PollStatus>> = {
  new_project: async (rid) => (await getNewProjectRequest(rid)) as NewProjectRequestStatus,
  story_plan: async (rid) => (await getStoryPlanRequest(rid)) as StoryPlanRequestStatus,
  story_write: async (rid) => (await getStoryWriteRequest(rid)) as StoryWriteRequestStatus,
  review: async (rid) => (await getReviewRequest(rid)) as ReviewRequestStatus,
  material_classify: async (rid) => (await getMaterialClassifyRequest(rid)) as ClassifyRequestStatus,
  material_distill: async (rid) => (await getMaterialDistillRequest(rid)) as BookDistillRequestStatus,
}

const cancellers: Record<AuthorTaskKind, (requestId: string) => Promise<unknown>> = {
  new_project: cancelNewProjectRequest,
  story_plan: cancelStoryPlanRequest,
  story_write: cancelStoryWriteRequest,
  review: cancelReviewRequest,
  material_classify: cancelMaterialClassifyRequest,
  material_distill: cancelMaterialDistillRequest,
}

const confirmers: Partial<Record<AuthorTaskKind, (task: AuthorTask) => Promise<unknown>> | Record<AuthorTaskKind, ((task: AuthorTask) => Promise<unknown>) | null>> = {
  new_project: (task) =>
    confirmNewProject({ proposal_token: (task.result as ProposeResult).proposal_token }),
  story_plan: (task) =>
    confirmStoryPlan({
      project_id: task.projectId as string,
      planning_token: (task.result as ProposeStoryPlanResult).planning_token,
    }),
  story_write: (task) =>
    confirmStoryWrite({
      project_id: task.projectId as string,
      writing_token: (task.result as ProposeStoryWriteResult).writing_token,
    }),
  review: null,
  material_classify: null,
  material_distill: null,
}

export function AuthorTaskCoordinatorProvider({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const [task, setTask] = useState<AuthorTask | null>(null)
  // 同步读写的最新任务（异步闭包用；避免过期 state）
  const taskRef = useRef<AuthorTask | null>(null)
  taskRef.current = task
  // 轮询会话：停止时自增；在途结果按会话丢弃
  const pollSessionRef = useRef(0)
  const pollTimerRef = useRef<number | null>(null)
  const resumedRef = useRef(false)
  // 阶段通知去重（waiting_author 的 phase/message 变化时通知一次）
  const notifiedPhaseKeyRef = useRef<string | null>(null)
  const notifiedFinalRef = useRef(false)

  const patchTask = useCallback((patch: Partial<AuthorTask>) => {
    setTask((current) => (current ? { ...current, ...patch } : current))
  }, [])

  const stopPolling = useCallback(() => {
    pollSessionRef.current += 1
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  const notifyOnce = useCallback(
    (message: string) => {
      actions.notify(message)
    },
    [actions],
  )

  /** 完成/失败通知：toast +（偏好开启时）真实提示音。 */
  const notifyFinal = useCallback(
    (message: string) => {
      actions.notify(message)
      if (state.preferences.sound) playCompletionSound()
    },
    [actions, state.preferences.sound],
  )

  // ---------------- 轮询（App 级：页面卸载不影响） ----------------

  const handlePollResult = useCallback(
    (kind: AuthorTaskKind, poll: PollStatus) => {
      const current = taskRef.current
      if (!current || current.kind !== kind) return
      const executionMode = current.execution?.execution_mode
      const status = deriveTaskStatus(kind, poll.status, poll.phase ?? null, executionMode)

      if (status === 'waiting_author') {
        // 阶段/消息变化时通知一次（story_write：pending_selection → pending_prose
        // 会再次全局宣布"请再次执行 /gowrite"）
        const message = poll.message ?? waitingAuthorMessage(kind, poll.phase ?? null)
        const key = kind === 'story_write' ? (poll.phase ?? message) : message
        if (notifiedPhaseKeyRef.current !== key) {
          notifiedPhaseKeyRef.current = key
          notifyOnce(message)
        }
        patchTask({ status, phase: poll.phase ?? null, message })
        return
      }
      if (status === 'running' || status === 'pending') {
        patchTask({ status: 'running', phase: null, message: poll.message ?? null })
        return
      }
      stopPolling()
      if (status === 'candidate') {
        const result = poll.result ?? null
        if (!result) {
          patchTask({ status: 'failed', error: '候选数据无效，请重新发起。' })
          if (!notifiedFinalRef.current) {
            notifiedFinalRef.current = true
            notifyFinal('候选数据无效，请重新发起。')
          }
          return
        }
        patchTask({ status: 'candidate', result, phase: null, message: null })
        if (!notifiedFinalRef.current) {
          notifiedFinalRef.current = true
          notifyFinal(candidateReadyMessage(kind))
        }
        return
      }
      if (status === 'canceled') {
        // 后端取消（显式取消由 cancel() 清理；这里兜底）
        setTask(null)
        return
      }
      // failed / expired
      patchTask({ status: 'failed', error: poll.error ?? '任务失败，请重新发起。' })
      if (!notifiedFinalRef.current) {
        notifiedFinalRef.current = true
        notifyFinal(poll.error ?? '任务失败，请重新发起。')
      }
    },
    [notifyFinal, notifyOnce, patchTask, stopPolling],
  )

  const startPolling = useCallback(
    (kind: AuthorTaskKind, requestId: string) => {
      stopPolling()
      const session = pollSessionRef.current + 1
      pollSessionRef.current = session
      const tick = async () => {
        if (pollSessionRef.current !== session) return
        try {
          const poll = await pollers[kind](requestId)
          if (pollSessionRef.current !== session) return
          handlePollResult(kind, poll)
          // 仍活跃则继续（candidate/failed/canceled 已 stopPolling）
          const t = taskRef.current
          if (t && t.kind === kind && isTaskActive(t.status)) {
            pollTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
          }
        } catch (e) {
          if (pollSessionRef.current !== session) return
          stopPolling()
          const current = taskRef.current
          if (current && current.kind === kind && isTaskActive(current.status)) {
            patchTask({ status: 'failed', error: toMessage(e) })
            if (!notifiedFinalRef.current) {
              notifiedFinalRef.current = true
              notifyFinal(toMessage(e))
            }
          }
        }
      }
      pollTimerRef.current = window.setTimeout(tick, 0)
    },
    [handlePollResult, notifyFinal, patchTask, stopPolling],
  )

  // ---------------- 启动 ----------------

  const start = useCallback(
    async (payload: TaskPayload): Promise<string | null> => {
      const current = taskRef.current
      if (current && isTaskActive(current.status)) {
        return '已有进行中的任务，请先完成或取消。'
      }
      const kind = payload.kind
      stopPolling()
      notifiedPhaseKeyRef.current = null
      notifiedFinalRef.current = false
      try {
        let prepared: {
          request_id?: string | null
          project_id?: string | null
          execution_mode?: string | null
          agent_id?: string | null
          model?: string | null
          phase?: string | null
          message?: string | null
          status?: string | null
        }
        switch (kind) {
          case 'new_project':
            prepared = await prepareNewProject({ name: payload.name, idea: payload.idea })
            break
          case 'story_plan':
            prepared = await prepareStoryPlan({ project_id: payload.project_id, author_question: payload.author_question })
            break
          case 'story_write':
            prepared = await prepareStoryWrite({
              project_id: payload.project_id,
              author_input: payload.author_input,
              chapter_number: payload.chapter_number,
            })
            break
          case 'review':
            prepared = await prepareReview({ project_id: payload.project_id, chapter_number: payload.chapter_number })
            break
          case 'material_classify':
            prepared = await classifyMaterialInbox()
            break
          case 'material_distill':
            prepared = await distillMaterial(payload.asset_id)
            break
        }
        const interactive = prepared.execution_mode !== 'direct'
        const next: AuthorTask = {
          kind,
          requestId: prepared.request_id ?? '',
          projectId: prepared.project_id ?? null,
          status: interactive ? 'waiting_author' : 'running',
          phase: prepared.phase ?? null,
          message: prepared.message ?? null,
          execution: {
            execution_mode: prepared.execution_mode,
            agent_id: prepared.agent_id ?? null,
            model: prepared.model ?? null,
          },
          result: null,
          error: null,
          meta: kind === 'material_distill' ? { asset_id: payload.asset_id } : null,
        }
        // material_classify / material_distill 同步完成（无 request_id）时直接进入候选
        if (kind === 'material_classify' || kind === 'material_distill') {
          const res = prepared as unknown as { status?: string; request_id?: string | null }
          if (res.status === 'ready' || res.status === 'completed') {
            next.status = 'candidate'
            next.result = prepared
            next.requestId = res.request_id ?? 'local'
          }
        }
        setTask(next)
        if (next.status === 'candidate') {
          if (!notifiedFinalRef.current) {
            notifiedFinalRef.current = true
            notifyFinal(candidateReadyMessage(kind))
          }
        } else if (next.status === 'waiting_author') {
          const message = next.message ?? waitingAuthorMessage(kind, next.phase)
          notifiedPhaseKeyRef.current = kind === 'story_write' ? (next.phase ?? message) : message
          notifyOnce(message)
        }
        if (next.status !== 'candidate') startPolling(kind, next.requestId)
        return null
      } catch (e) {
        const message = toMessage(e)
        setTask({
          kind,
          requestId: '',
          projectId: 'project_id' in payload ? payload.project_id : null,
          status: 'failed',
          phase: null,
          message: null,
          execution: null,
          result: null,
          error: message,
        })
        return message
      }
    },
    [notifyFinal, notifyOnce, startPolling, stopPolling],
  )

  // ---------------- 取消 / 确认 / 消费 / 导航 ----------------

  const cancel = useCallback(async () => {
    const current = taskRef.current
    if (!current) return
    stopPolling()
    const requestId = current.requestId
    setTask(null)
    notifiedPhaseKeyRef.current = null
    notifiedFinalRef.current = false
    if (requestId && requestId !== 'local') {
      try {
        await cancellers[current.kind](requestId)
      } catch {
        // 取消尽力而为；本地任务已清
      }
    }
  }, [stopPolling])

  const confirm = useCallback(
    async (kind: 'new_project' | 'story_plan' | 'story_write'): Promise<unknown | null> => {
      const current = taskRef.current
      if (!current || current.kind !== kind || current.status !== 'candidate') return null
      const confirmer = confirmers[kind]
      if (!confirmer) return null
      patchTask({ status: 'confirming', error: null })
      try {
        const result = await confirmer(current)
        // 成功：任务完成，结果已消费（页面自行刷新正式面）
        stopPolling()
        setTask(null)
        notifiedPhaseKeyRef.current = null
        notifiedFinalRef.current = false
        return result
      } catch (e) {
        // 失败：候选保留可见，展示真实后端错误
        patchTask({ status: 'candidate', error: toMessage(e) })
        return null
      }
    },
    [patchTask, stopPolling],
  )

  const consume = useCallback(() => {
    stopPolling()
    setTask(null)
    notifiedPhaseKeyRef.current = null
    notifiedFinalRef.current = false
  }, [stopPolling])

  const navigateToTask = useCallback(() => {
    const current = taskRef.current
    if (!current) return
    const target = taskTarget(current.kind)
    if (target.section) actions.setProjectSection(target.section)
    else actions.navigate(target.page ?? 'works')
  }, [actions])

  // ---------------- remount/reload 恢复（幂等一次） ----------------

  const resume = useCallback(async () => {
    if (resumedRef.current) return
    resumedRef.current = true
    if (taskRef.current) return
    try {
      const facts = await getActiveAuthorOperation()
      if (!facts || !facts.request_id) return
      const kind = facts.kind as AuthorTaskKind
      if (!kind || !pollers[kind]) return
      if (facts.state === 'orphaned') {
        // Direct worker 已不存在（进程重启）：fail closed，绝不显示假 running
        notifyFinal(facts.message ?? '直连任务已失效，请重新发起。')
        void cancellers[kind](facts.request_id).catch(() => {})
        return
      }
      notifiedPhaseKeyRef.current = null
      notifiedFinalRef.current = false
      const interactive = facts.execution_mode === 'interactive_bridge'
      const next: AuthorTask = {
        kind,
        requestId: facts.request_id,
        projectId: facts.project_id,
        status: interactive ? 'waiting_author' : 'running',
        phase: facts.phase,
        message: facts.message,
        execution: {
          execution_mode: facts.execution_mode,
          agent_id: facts.agent_id,
          model: facts.model,
        },
        result: null,
        error: null,
      }
      setTask(next)
      if (interactive) {
        const message = facts.message ?? waitingAuthorMessage(kind, facts.phase)
        notifiedPhaseKeyRef.current = kind === 'story_write' ? (facts.phase ?? message) : message
      }
      startPolling(kind, facts.request_id)
    } catch {
      // 恢复失败静默：下次刷新/操作可再次尝试
    }
  }, [notifyFinal, startPolling])

  useEffect(() => {
    void resume()
  }, [resume])

  // 卸载（应用关闭/StrictMode 重挂载）时：不停止轮询（任务属于 Go Write，
  // 不随组件卸载取消）；重挂载后允许再次 resume（StrictMode 开发模式）
  useEffect(() => {
    return () => {
      resumedRef.current = false
    }
  }, [])

  const controller = useMemo<AuthorTaskController>(
    () => ({ task, start, cancel, confirm, consume, navigateToTask, resume }),
    [task, start, cancel, confirm, consume, navigateToTask, resume],
  )

  return <AuthorTaskContext.Provider value={controller}>{children}</AuthorTaskContext.Provider>
}

export function useAuthorTask(): AuthorTaskController {
  const value = useContext(AuthorTaskContext)
  if (!value) throw new Error('useAuthorTask must be inside AuthorTaskCoordinatorProvider')
  return value
}

export type { ConfirmResult, ConfirmStoryPlanResult, ConfirmStoryWriteResult, ReviewReport }
