import { isTaskActive, type AuthorTask, type AuthorTaskKind } from './taskModel'

export type AuthorTasksByRequestId = Record<string, AuthorTask>

export interface TaskStartDescriptor {
  kind: AuthorTaskKind
  assetId?: string | null
}

export const taskList = (tasks: AuthorTasksByRequestId): AuthorTask[] => Object.values(tasks)

export function putTask(tasks: AuthorTasksByRequestId, task: AuthorTask): AuthorTasksByRequestId {
  return { ...tasks, [task.requestId]: task }
}

export function patchRequestTask(
  tasks: AuthorTasksByRequestId,
  requestId: string,
  patch: Partial<AuthorTask>,
): AuthorTasksByRequestId {
  const current = tasks[requestId]
  return current ? putTask(tasks, { ...current, ...patch }) : tasks
}

export function dropTask(tasks: AuthorTasksByRequestId, requestId: string): AuthorTasksByRequestId {
  if (!(requestId in tasks)) return tasks
  const next = { ...tasks }
  delete next[requestId]
  return next
}

export function taskFor(tasks: AuthorTasksByRequestId, kind: AuthorTaskKind, projectId?: string | null): AuthorTask | null {
  return taskList(tasks).find((task) => (
    task.kind === kind && (!projectId || !task.projectId || task.projectId === projectId)
  )) ?? null
}

/** Backend execution is active; retained material candidates/errors are not. */
export function isTaskExecuting(task: AuthorTask): boolean {
  return task.status === 'pending'
    || task.status === 'running'
    || task.status === 'waiting_author'
    || task.status === 'confirming'
}

/** Stable key used by auto-copy/notification de-duplication per waiting phase. */
export function waitingPhaseKey(task: AuthorTask): string {
  return `${task.requestId}:${task.phase || 'waiting'}`
}

function descriptorFor(task: AuthorTask): TaskStartDescriptor {
  return {
    kind: task.kind,
    assetId: task.kind === 'material_distill' && typeof task.meta?.asset_id === 'string'
      ? task.meta.asset_id
      : null,
  }
}

/** Admission rule for real tasks plus starts whose backend prepare call is in flight. */
export function startConflict(
  tasks: AuthorTasksByRequestId,
  next: TaskStartDescriptor,
  provisional: TaskStartDescriptor[] = [],
): string | null {
  const open = taskList(tasks)
    .filter((task) => task.kind === 'material_distill' ? isTaskExecuting(task) : isTaskActive(task.status))
    .map(descriptorFor)
    .concat(provisional)

  if (next.kind === 'material_distill') {
    if (open.some((item) => item.kind !== 'material_distill')) return '已有其他作者任务，请先完成或取消。'
    if (next.assetId && open.some((item) => item.kind === 'material_distill' && item.assetId === next.assetId)) {
      return '该素材正在学习，请等待完成或取消当前任务。'
    }
    return null
  }
  if (open.some((item) => item.kind === 'material_distill')) {
    return '素材学习正在进行，请等待完成或取消后再开始此任务。'
  }
  if (open.some((item) => item.kind !== 'material_distill')) return '已有进行中的任务，请先完成或取消。'
  return null
}
