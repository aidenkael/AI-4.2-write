/** App-level, request-keyed owner of every Author Operation UI lifecycle. */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
  type ReactNode,
} from 'react'
import {
  cancelMaterialDistillRequest, cancelNewProjectRequest, cancelReviewRequest,
  cancelStoryPlanRequest, cancelStoryWriteRequest, cancelFoundationDesignRequest,
  confirmNewProject, confirmStoryPlan, confirmStoryWrite, confirmFoundationDesign,
  getActiveAuthorOperations, getMaterialDistillRequest, getNewProjectRequest,
  getReviewRequest, getStoryPlanRequest, getStoryWriteRequest, getFoundationDesignRequest,
  prepareNewProject, prepareReview, prepareStoryPlan, prepareStoryWrite,
  prepareFoundationDesign, distillMaterial,
  type BookDistillRequestStatus, type ConfirmResult, type ConfirmStoryPlanResult,
  type ConfirmStoryWriteResult, type NewProjectRequestStatus, type ProposeResult,
  type ProposeStoryPlanResult, type ProposeStoryWriteResult, type FoundationDesignResult,
  type FoundationDesignItem, type FoundationDesignDomainRelation, type ReviewReport,
  type ReviewRequestStatus, type StoryPlanRequestStatus, type StoryWriteRequestStatus,
} from '../../bridge/client'
import { useApp } from '../app/AppStore'
import { playCompletionSound } from './sound'
import {
  candidateReadyMessage, deriveTaskStatus, taskTarget, waitingAuthorMessage,
  type AuthorTask, type AuthorTaskKind,
} from './taskModel'
import {
  dropTask, isTaskExecuting, patchRequestTask, putTask, resolveTaskStartFacts, startConflict, waitingPhaseKey,
  type AuthorTasksByRequestId, type TaskStartDescriptor,
} from './coordinatorModel'

const POLL_INTERVAL_MS = 700
const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export type TaskPayload =
  | { kind: 'new_project'; name: string; idea: string }
  | { kind: 'story_plan'; project_id: string; author_question: string; planning_mode?: string; impact_candidate_ids?: string[]; stage_ref?: string; chapter_range?: number[] }
  | { kind: 'story_write'; project_id: string; author_input: string; chapter_number?: number }
  | { kind: 'review'; project_id: string; chapter_number?: number }
  | { kind: 'material_distill'; asset_id: string; asset_name?: string }
  | { kind: 'foundation_design'; project_id: string; author_request: string; base_model_rev: number }

type ConfirmExtra = { items?: unknown[]; relations?: unknown[]; base_model_rev?: number }

export interface AuthorTaskController {
  tasksByRequestId: AuthorTasksByRequestId
  start(payload: TaskPayload): Promise<string | null>
  cancel(requestId: string): Promise<void>
  confirm(requestId: string, kind: 'new_project' | 'story_plan' | 'story_write' | 'foundation_design', extra?: ConfirmExtra): Promise<unknown | null>
  consume(requestId: string): void
  navigateToTask(requestId: string): void
  resume(): Promise<void>
}

export const AuthorTaskContext = createContext<AuthorTaskController | null>(null)

type PollStatus = {
  status: string
  phase?: string | null
  execution_phase?: string | null
  execution_mode?: string | null
  agent_id?: string | null
  model?: string | null
  agent_command?: string | null
  message?: string | null
  result?: unknown | null
  error?: string | null
}

const pollers: Record<AuthorTaskKind, (requestId: string) => Promise<PollStatus>> = {
  new_project: async (rid) => (await getNewProjectRequest(rid)) as NewProjectRequestStatus,
  story_plan: async (rid) => (await getStoryPlanRequest(rid)) as StoryPlanRequestStatus,
  story_write: async (rid) => (await getStoryWriteRequest(rid)) as StoryWriteRequestStatus,
  review: async (rid) => (await getReviewRequest(rid)) as ReviewRequestStatus,
  material_distill: async (rid) => (await getMaterialDistillRequest(rid)) as BookDistillRequestStatus,
  foundation_design: async (rid) => await getFoundationDesignRequest(rid),
}

const cancellers: Record<AuthorTaskKind, (requestId: string) => Promise<unknown>> = {
  new_project: cancelNewProjectRequest,
  story_plan: cancelStoryPlanRequest,
  story_write: cancelStoryWriteRequest,
  review: cancelReviewRequest,
  material_distill: cancelMaterialDistillRequest,
  foundation_design: cancelFoundationDesignRequest,
}

const confirmers: Partial<Record<AuthorTaskKind, ((task: AuthorTask, extra?: ConfirmExtra) => Promise<unknown>) | null>> = {
  new_project: (task) => confirmNewProject({ proposal_token: (task.result as ProposeResult).proposal_token }),
  story_plan: (task) => confirmStoryPlan({ project_id: task.projectId as string, planning_token: (task.result as ProposeStoryPlanResult).planning_token }),
  story_write: (task) => confirmStoryWrite({ project_id: task.projectId as string, writing_token: (task.result as ProposeStoryWriteResult).writing_token }),
  foundation_design: (task, extra) => confirmFoundationDesign({
    project_id: task.projectId as string,
    proposal_token: (task.result as FoundationDesignResult).proposal_token,
    items: (extra?.items ?? []) as FoundationDesignItem[],
    relations: (extra?.relations ?? []) as FoundationDesignDomainRelation[],
    base_model_rev: extra?.base_model_rev ?? 0,
  }),
  review: null,
  material_distill: null,
}

async function copyExactCommand(command: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(command); return true } catch { /* desktop fallback */ }
  try {
    const input = document.createElement('textarea')
    input.value = command
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    const ok = document.execCommand('copy')
    input.remove()
    return ok
  } catch { return false }
}

const descriptor = (payload: TaskPayload): TaskStartDescriptor => ({
  kind: payload.kind,
  assetId: payload.kind === 'material_distill' ? payload.asset_id : null,
})

export function AuthorTaskCoordinatorProvider({ children }: { children: ReactNode }) {
  const { state, actions } = useApp()
  const [tasksByRequestId, setTasksByRequestId] = useState<AuthorTasksByRequestId>({})
  const tasksRef = useRef<AuthorTasksByRequestId>({})
  const provisionalStartsRef = useRef<TaskStartDescriptor[]>([])
  const resumedRef = useRef(false)
  const pollTimerRef = useRef<number | null>(null)
  const pollRunningRef = useRef(false)
  const notifiedWaitingRef = useRef(new Set<string>())
  const copiedWaitingRef = useRef(new Set<string>())
  const notifiedFinalRef = useRef(new Set<string>())

  const replaceTasks = useCallback((next: AuthorTasksByRequestId) => {
    tasksRef.current = next
    setTasksByRequestId(next)
  }, [])

  const patchTask = useCallback((requestId: string, patch: Partial<AuthorTask>) => {
    const current = tasksRef.current[requestId]
    if (current) replaceTasks(patchRequestTask(tasksRef.current, requestId, patch))
  }, [replaceTasks])

  const removeTask = useCallback((requestId: string) => {
    replaceTasks(dropTask(tasksRef.current, requestId))
    for (const key of notifiedWaitingRef.current) if (key.startsWith(`${requestId}:`)) notifiedWaitingRef.current.delete(key)
    for (const key of copiedWaitingRef.current) if (key.startsWith(`${requestId}:`)) copiedWaitingRef.current.delete(key)
    notifiedFinalRef.current.delete(requestId)
  }, [replaceTasks])

  const notifyFinal = useCallback((requestId: string, message: string) => {
    if (notifiedFinalRef.current.has(requestId)) return
    notifiedFinalRef.current.add(requestId)
    actions.notify(message)
    if (state.preferences.sound) playCompletionSound()
  }, [actions, state.preferences.sound])

  const announceWaiting = useCallback((task: AuthorTask) => {
    const key = waitingPhaseKey(task)
    const command = task.execution?.agent_command
    if (command && !copiedWaitingRef.current.has(key)) {
      copiedWaitingRef.current.add(key)
      void copyExactCommand(command).then((copied) => {
        actions.notify(copied
          ? `已复制 ${command}，请在 Qoder 中执行。`
          : '自动复制失败，请点击复制')
      })
    }
    if (!notifiedWaitingRef.current.has(key)) {
      notifiedWaitingRef.current.add(key)
      if (!command) actions.notify(task.message ?? waitingAuthorMessage(task.kind, task.phase))
    }
  }, [actions])

  const handlePollResult = useCallback((requestId: string, poll: PollStatus) => {
    const current = tasksRef.current[requestId]
    if (!current || !isTaskExecuting(current)) return
    const executionMode = poll.execution_mode ?? current.execution?.execution_mode
    const status = poll.execution_phase === 'running'
      ? 'running'
      : deriveTaskStatus(current.kind, poll.status, poll.phase ?? null, executionMode)
    const execution = {
      ...(current.execution ?? {}),
      execution_mode: executionMode ?? null,
      agent_id: poll.agent_id ?? current.execution?.agent_id ?? null,
      model: poll.model ?? current.execution?.model ?? null,
      agent_command: poll.agent_command ?? current.execution?.agent_command ?? null,
      execution_phase: poll.execution_phase ?? current.execution?.execution_phase ?? null,
    }
    if (status === 'waiting_author') {
      const next: AuthorTask = {
        ...current,
        status,
        phase: poll.phase ?? current.phase,
        message: poll.message ?? waitingAuthorMessage(current.kind, poll.phase ?? current.phase),
        execution,
      }
      replaceTasks(putTask(tasksRef.current, next))
      announceWaiting(next)
      return
    }
    if (status === 'running' || status === 'pending') {
      patchTask(requestId, { status: 'running', message: poll.message ?? 'Agent 正在执行', execution })
      return
    }
    if (status === 'candidate') {
      if (!poll.result) {
        const error = '候选数据无效，请重新发起。'
        patchTask(requestId, { status: 'failed', error })
        notifyFinal(requestId, error)
      } else {
        patchTask(requestId, { status: 'candidate', result: poll.result, phase: null, message: null, execution })
        notifyFinal(requestId, candidateReadyMessage(current.kind))
      }
      return
    }
    if (status === 'canceled') { removeTask(requestId); return }
    const error = poll.status === 'expired' ? '等待 Agent 超时，请重新发起。' : (poll.error ?? '任务失败，请重新发起。')
    patchTask(requestId, { status: 'failed', error, execution })
    notifyFinal(requestId, error)
  }, [announceWaiting, notifyFinal, patchTask, removeTask, replaceTasks])

  const pollTick = useCallback(async () => {
    if (pollRunningRef.current) return
    pollRunningRef.current = true
    const snapshot = Object.values(tasksRef.current).filter((task) => isTaskExecuting(task) && !task.requestId.startsWith('local:'))
    const results = await Promise.all(snapshot.map(async (task) => {
      try { return { task, poll: await pollers[task.kind](task.requestId), error: null as string | null } }
      catch (e) { return { task, poll: null, error: toMessage(e) } }
    }))
    pollRunningRef.current = false
    for (const item of results) {
      if (!tasksRef.current[item.task.requestId]) continue
      if (item.error) {
        patchTask(item.task.requestId, { status: 'failed', error: item.error })
        notifyFinal(item.task.requestId, item.error)
      } else if (item.poll) handlePollResult(item.task.requestId, item.poll)
    }
    const remaining = Object.values(tasksRef.current).some((task) => isTaskExecuting(task) && !task.requestId.startsWith('local:'))
    pollTimerRef.current = remaining ? window.setTimeout(() => void pollTick(), POLL_INTERVAL_MS) : null
  }, [handlePollResult, notifyFinal, patchTask])

  const ensurePolling = useCallback(() => {
    if (pollTimerRef.current === null && !pollRunningRef.current) {
      pollTimerRef.current = window.setTimeout(() => {
        pollTimerRef.current = null
        void pollTick()
      }, 0)
    }
  }, [pollTick])

  const start = useCallback(async (payload: TaskPayload): Promise<string | null> => {
    const nextDescriptor = descriptor(payload)
    const conflict = startConflict(tasksRef.current, nextDescriptor, provisionalStartsRef.current)
    if (conflict) return conflict
    provisionalStartsRef.current = [...provisionalStartsRef.current, nextDescriptor]
    try {
      let prepared: {
        request_id?: string | null; project_id?: string | null; execution_mode?: string | null
        agent_id?: string | null; model?: string | null; phase?: string | null
        execution_phase?: string | null; agent_command?: string | null
        message?: string | null; status?: string | null
      }
      switch (payload.kind) {
        case 'new_project': prepared = await prepareNewProject({ name: payload.name, idea: payload.idea }); break
        case 'story_plan': prepared = await prepareStoryPlan({ project_id: payload.project_id, author_question: payload.author_question, planning_mode: payload.planning_mode, impact_candidate_ids: payload.impact_candidate_ids, stage_ref: payload.stage_ref, chapter_range: payload.chapter_range }); break
        case 'story_write': prepared = await prepareStoryWrite({ project_id: payload.project_id, author_input: payload.author_input, chapter_number: payload.chapter_number }); break
        case 'review': prepared = await prepareReview({ project_id: payload.project_id, chapter_number: payload.chapter_number }); break
        case 'material_distill': prepared = await distillMaterial(payload.asset_id); break
        case 'foundation_design': prepared = await prepareFoundationDesign({ project_id: payload.project_id, author_request: payload.author_request, base_model_rev: payload.base_model_rev }); break
      }
      const facts = prepared.request_id
        ? (await getActiveAuthorOperations().catch(() => [])).find((item) => item.request_id === prepared.request_id)
        : null
      const requestId = prepared.request_id ?? `local:${Date.now()}:${Math.random().toString(16).slice(2)}`
      const startFacts = resolveTaskStartFacts(payload.kind, prepared, facts)
      const task: AuthorTask = {
        kind: payload.kind,
        requestId,
        projectId: prepared.project_id ?? ('project_id' in payload ? payload.project_id : null),
        status: startFacts.status,
        phase: startFacts.phase,
        message: prepared.message ?? facts?.message ?? null,
        execution: startFacts.execution,
        result: null,
        error: null,
        meta: payload.kind === 'material_distill' ? { asset_id: payload.asset_id, target_label: payload.asset_name ?? facts?.target_label ?? null } : null,
      }
      if (payload.kind === 'material_distill' && (prepared.status === 'ready' || prepared.status === 'completed')) {
        task.status = 'candidate'
        task.result = prepared
      }
      replaceTasks(putTask(tasksRef.current, task))
      if (task.status === 'waiting_author') announceWaiting(task)
      else if (task.status === 'candidate') notifyFinal(requestId, candidateReadyMessage(task.kind))
      else ensurePolling()
      return null
    } catch (e) {
      return toMessage(e)
    } finally {
      const index = provisionalStartsRef.current.indexOf(nextDescriptor)
      if (index >= 0) provisionalStartsRef.current = provisionalStartsRef.current.filter((_, i) => i !== index)
    }
  }, [announceWaiting, ensurePolling, notifyFinal, replaceTasks])

  const cancel = useCallback(async (requestId: string) => {
    const current = tasksRef.current[requestId]
    if (!current) return
    removeTask(requestId)
    if (!requestId.startsWith('local:')) {
      try { await cancellers[current.kind](requestId) } catch { /* scoped local removal remains */ }
    }
  }, [removeTask])

  const confirm = useCallback(async (requestId: string, kind: 'new_project' | 'story_plan' | 'story_write' | 'foundation_design', extra?: ConfirmExtra): Promise<unknown | null> => {
    const current = tasksRef.current[requestId]
    if (!current || current.kind !== kind || current.status !== 'candidate') return null
    const confirmer = confirmers[kind]
    if (!confirmer) return null
    patchTask(requestId, { status: 'confirming', error: null })
    try {
      const result = await confirmer(current, extra)
      removeTask(requestId)
      return result
    } catch (e) {
      patchTask(requestId, { status: 'candidate', error: toMessage(e) })
      return null
    }
  }, [patchTask, removeTask])

  const consume = useCallback((requestId: string) => removeTask(requestId), [removeTask])

  const navigateToTask = useCallback((requestId: string) => {
    const current = tasksRef.current[requestId]
    if (!current) return
    const target = taskTarget(current.kind)
    if (target.section) actions.setProjectSection(target.section)
    else actions.navigate(target.page ?? 'works')
  }, [actions])

  const resume = useCallback(async () => {
    if (resumedRef.current) return
    resumedRef.current = true
    try {
      const factsList = await getActiveAuthorOperations()
      const recovered: AuthorTasksByRequestId = { ...tasksRef.current }
      const waiting: AuthorTask[] = []
      let hasPolling = false
      for (const facts of factsList) {
        const kind = facts.kind as AuthorTaskKind
        if (!facts.request_id || !pollers[kind]) continue
        const orphaned = facts.state === 'orphaned'
        const task: AuthorTask = {
          kind,
          requestId: facts.request_id,
          projectId: facts.project_id,
          status: orphaned
            ? 'failed'
            : facts.execution_phase === 'running'
              ? 'running'
              : deriveTaskStatus(kind, 'pending', facts.phase, facts.execution_mode),
          phase: facts.phase,
          message: facts.message,
          execution: { execution_mode: facts.execution_mode, agent_id: facts.agent_id, model: facts.model, agent_command: facts.agent_command, execution_phase: facts.execution_phase },
          result: null,
          error: orphaned ? (facts.message ?? '直连任务已失效，请重新发起。') : null,
          meta: kind === 'material_distill' ? { asset_id: facts.asset_id, target_label: facts.target_label } : null,
        }
        recovered[task.requestId] = task
        if (task.status === 'waiting_author') waiting.push(task)
        if (isTaskExecuting(task)) hasPolling = true
        if (orphaned) notifyFinal(task.requestId, task.error as string)
      }
      replaceTasks(recovered)
      waiting.forEach(announceWaiting)
      if (hasPolling) ensurePolling()
    } catch { resumedRef.current = false }
  }, [announceWaiting, ensurePolling, notifyFinal, replaceTasks])

  useEffect(() => { void resume() }, [resume])
  useEffect(() => () => {
    if (pollTimerRef.current !== null) window.clearTimeout(pollTimerRef.current)
    pollTimerRef.current = null
    resumedRef.current = false
  }, [])

  const controller = useMemo<AuthorTaskController>(() => ({
    tasksByRequestId, start, cancel, confirm, consume, navigateToTask, resume,
  }), [tasksByRequestId, start, cancel, confirm, consume, navigateToTask, resume])

  return <AuthorTaskContext.Provider value={controller}>{children}</AuthorTaskContext.Provider>
}

export function useAuthorTask(): AuthorTaskController {
  const value = useContext(AuthorTaskContext)
  if (!value) throw new Error('useAuthorTask must be inside AuthorTaskCoordinatorProvider')
  return value
}

export type { ConfirmResult, ConfirmStoryPlanResult, ConfirmStoryWriteResult, ReviewReport }
