/**
 * 故事规划真实 StoryPlan 消费者控制器（App 级协调器消费者）。
 *
 * 根不变量：AI 任务属于 Go Write（AuthorTaskCoordinator），不属于页面。
 * 本控制器只保留页面本地数据（正式概览、作者问题），任务状态全部来自
 * 协调器；离开页面任务继续推进、候选保留，返回后自动附着。
 *
 * 约束：
 * - 候选是后端返回的单个候选 { proposal, planning_items[] }，只读；
 * - confirm 只回传 { project_id, planning_token }；
 * - 换项目绝不把另一项目的任务/候选带到本页（按 projectId 过滤展示）。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getProjectOverview,
  type ProjectOverview,
  type StoryPlanCandidate,
} from '../../bridge/client'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'

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
  generate(options?: {
    planningMode?: string
    impactCandidateIds?: string[]
    stageRef?: string
    chapterRange?: number[]
  }): Promise<void>
  cancel(): Promise<void>
  discard(): Promise<void>
  regenerate(): Promise<void>
  confirm(): Promise<void>
  reloadOverview(): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

function taskViewForProject(
  task: ReturnType<typeof useAuthorTask>['task'],
  projectId: string | null,
): Pick<DevelopmentControllerState, 'requestId' | 'planningToken' | 'candidate' | 'backendMessage' | 'status' | 'error' | 'execution'> | null {
  if (!task || task.kind !== 'story_plan') return null
  if (projectId && task.projectId && task.projectId !== projectId) return null
  const base = {
    requestId: task.requestId || null,
    planningToken: null as string | null,
    candidate: null as StoryPlanCandidate | null,
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
      const result = task.result as { planning_token?: string; candidate?: StoryPlanCandidate; message?: string } | null
      return {
        ...base,
        status: 'waiting_confirmation',
        planningToken: result?.planning_token ?? null,
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

export function useDevelopmentController(options: {
  projectId: string | null
  notify?: (message: string) => void
}): DevelopmentController {
  const { projectId, notify } = options
  const { task, start, cancel: cancelTask, confirm: confirmTask } = useAuthorTask()
  const [overview, setOverview] = useState<ProjectOverview | null>(null)
  const [overviewLoading, setOverviewLoading] = useState(false)
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [authorQuestion, setAuthorQuestionState] = useState('')
  const [acceptedNote, setAcceptedNote] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId

  const loadOverview = useCallback(async (pid: string) => {
    setOverviewLoading(true)
    setOverviewError(null)
    try {
      const next = await getProjectOverview(pid)
      if (projectRef.current !== pid) return
      setOverview(next)
    } catch (e) {
      if (projectRef.current !== pid) return
      setOverviewError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setOverviewLoading(false)
    }
  }, [])

  useEffect(() => {
    setAcceptedNote(false)
    setLocalError(null)
    if (!projectId) {
      setOverview(null)
      setOverviewLoading(false)
      return
    }
    void loadOverview(projectId)
  }, [projectId, loadOverview])

  const view = taskViewForProject(task, projectId)
  const candidate = view?.candidate ?? null

  const state: DevelopmentControllerState = {
    overview,
    overviewLoading,
    overviewError,
    authorQuestion,
    requestId: view?.requestId ?? null,
    planningToken: view?.planningToken ?? null,
    candidate,
    backendMessage: view?.backendMessage ?? null,
    status: view?.status ?? (acceptedNote ? 'accepted' : 'idle'),
    error: view?.error ?? overviewError ?? localError,
    execution: view?.execution ?? null,
  }

  const setAuthorQuestion = useCallback((input: string) => {
    setAuthorQuestionState(input)
    setLocalError(null)
  }, [])

  const generate = useCallback(async (options?: {
    planningMode?: string
    impactCandidateIds?: string[]
    stageRef?: string
    chapterRange?: number[]
  }) => {
    const pid = projectRef.current
    const question = authorQuestion.trim()
    const isImpactReplan = options?.planningMode === 'impact_replan'
    const structuredMode = options?.planningMode && options.planningMode !== 'free'
    if (!pid) {
      setLocalError('请先选择正式作品。')
      return
    }
    if (!question && !structuredMode) {
      setLocalError('请先写下你想一起想的问题。')
      return
    }
    if (isImpactReplan && !(options?.impactCandidateIds ?? []).length) {
      setLocalError('重新规划受影响内容必须选择至少一个影响候选。')
      return
    }
    if (options?.planningMode === 'stage' && !options.stageRef) {
      setLocalError('请先选择一个真实的卷/阶段。')
      return
    }
    if (options?.planningMode === 'near_term' && !(options.chapterRange ?? []).length) {
      setLocalError('请先给出近期细化的章节范围。')
      return
    }
    setAcceptedNote(false)
    const busy = await start({
      kind: 'story_plan',
      project_id: pid,
      author_question: question,
      planning_mode: options?.planningMode,
      impact_candidate_ids: options?.impactCandidateIds,
      stage_ref: options?.stageRef,
      chapter_range: options?.chapterRange,
    })
    if (busy) setLocalError(busy)
  }, [authorQuestion, start])

  const cancel = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const discard = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const regenerate = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
    await generate()
  }, [cancelTask, generate])
  const confirm = useCallback(async () => {
    const pid = projectRef.current
    if (!pid || !candidate) {
      setLocalError('缺少确认信息，请重新发起。')
      return
    }
    try {
      const confirmed = await confirmTask('story_plan')
      if (!confirmed) {
        setLocalError(task?.error ?? '确认失败，请重试。')
        return
      }
      await loadOverview(pid)
      setAcceptedNote(true)
      notify?.((confirmed as { message?: string }).message || '规划已确认并写入。')
    } catch (e) {
      setLocalError(toMessage(e))
    }
  }, [candidate, confirmTask, loadOverview, notify, task?.error])

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
