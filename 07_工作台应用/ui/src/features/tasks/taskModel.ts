/**
 * Author Task 纯状态模型（无 React / DOM 依赖，可被 node:test 直接测试）。
 *
 * 根不变量：AI 任务属于 Go Write（App 级协调器），不属于挂载的页面组件。
 * 本模块只做确定性的状态派生与展示文本，不持有任何计时器/请求。
 */
import type { GlobalPage, ProjectSection } from '../../contracts/ui'

export type AuthorTaskKind =
  | 'new_project'
  | 'story_plan'
  | 'story_write'
  | 'review'
  | 'material_classify'
  | 'material_distill'
  | 'foundation_design'

/** 协调器任务状态（与后端轮询状态解耦的 App 级投影）。 */
export type AuthorTaskStatus =
  | 'pending' // 刚准备，尚未开始轮询
  | 'running' // 后台执行中（Direct）
  | 'waiting_author' // 等待作者动作（Interactive /gowrite）
  | 'candidate' // 结果已就绪，等待确认/丢弃/消费
  | 'confirming' // 作者确认请求在途
  | 'failed' // 失败（结果保留到页面消费/重试）
  | 'canceled' // 已取消（立即清理）

export interface AuthorTaskExecution {
  execution_mode?: string | null
  agent_id?: string | null
  model?: string | null
}

export interface AuthorTask {
  kind: AuthorTaskKind
  requestId: string
  /** new_project 在创建前没有 project_id；其余操作恒有。 */
  projectId: string | null
  status: AuthorTaskStatus
  /** story_write 交互阶段：pending_selection / pending_prose。 */
  phase: string | null
  /** 后端返回的作者可读消息（绝不伪造进度）。 */
  message: string | null
  execution: AuthorTaskExecution | null
  /** 每类操作的候选/报告/计划载荷（消费前保留在协调器）。 */
  result: unknown | null
  error: string | null
  /** 非机密补充元数据（如 material_distill 的 asset_id；仅页面展示用）。 */
  meta?: Record<string, unknown> | null
}

export interface TaskTarget {
  page?: GlobalPage
  section?: ProjectSection
}

export const TASK_LABELS: Record<AuthorTaskKind, string> = {
  new_project: '新建作品',
  story_plan: '大纲与规划',
  story_write: '正文写作',
  review: '作品检查',
  material_classify: '素材分类',
  material_distill: '素材蒸馏',
  foundation_design: '完善作品地基',
}

export function taskLabel(kind: AuthorTaskKind): string {
  return TASK_LABELS[kind]
}

export function taskTarget(kind: AuthorTaskKind): TaskTarget {
  switch (kind) {
    case 'new_project':
      return { page: 'works' }
    case 'story_plan':
      return { section: 'planning' }
    case 'story_write':
      return { section: 'writing' }
    case 'review':
      return { section: 'review' }
    case 'material_classify':
    case 'material_distill':
      return { page: 'materials' }
    case 'foundation_design':
      return { section: 'foundation' }
  }
}

/**
 * 后端轮询状态 → 协调器状态（纯函数；execution_mode 决定交互/直连展示）。
 * 绝不编造状态：pending 无 phase 且 direct → running；交互 → waiting_author。
 */
export function deriveTaskStatus(
  _kind: AuthorTaskKind,
  pollStatus: string,
  phase: string | null,
  executionMode: string | null | undefined,
): AuthorTaskStatus {
  if (pollStatus === 'completed') return 'candidate'
  if (pollStatus === 'canceled') return 'canceled'
  if (pollStatus === 'failed' || pollStatus === 'expired') return 'failed'
  if (pollStatus !== 'pending') return 'failed'
  if (executionMode === 'interactive_bridge') return 'waiting_author'
  if (phase === 'pending_selection' || phase === 'pending_prose') return 'waiting_author'
  return 'running'
}

/** 等待作者动作时的默认提示（phase 特化；与后端消息一致，绝不伪造）。 */
export function waitingAuthorMessage(kind: AuthorTaskKind, phase: string | null): string {
  if (kind === 'story_write') {
    if (phase === 'pending_prose') return '上下文已准备好，请再次执行 /gowrite 生成正文'
    return '等待 Qoder /gowrite：正在选择本次写作上下文'
  }
  if (kind === 'material_classify') return '等待 Qoder /gowrite：正在分类待入库素材'
  if (kind === 'material_distill') return '等待 Qoder /gowrite：正在蒸馏知识'
  return '等待 Qoder /gowrite 执行任务'
}

/** 候选就绪通知文本（通知一次；不重复）。 */
export function candidateReadyMessage(kind: AuthorTaskKind): string {
  switch (kind) {
    case 'new_project':
      return '新建作品候选已生成 · 返回查看'
    case 'story_plan':
      return '规划候选已生成 · 返回查看'
    case 'story_write':
      return '正文候选已生成 · 返回查看'
    case 'review':
      return '检查报告已生成 · 返回查看'
    case 'material_classify':
      return '入库建议已生成 · 返回查看'
    case 'material_distill':
      return '蒸馏完成 · 返回查看'
    case 'foundation_design':
      return '作品地基候选已生成 · 返回查看'
  }
}

export interface TaskStripView {
  label: string
  stateText: string
  /** primary 动作类型：gowrite = 需要作者去执行 /gowrite；return = 返回任务页。 */
  primaryAction: 'gowrite' | 'return'
  primaryLabel: string
  canCancel: boolean
}

/**
 * 全局任务条投影（纯函数）：只显示真实状态；Agent/执行模式只作次要细节。
 */
export function taskStripView(task: AuthorTask): TaskStripView {
  const label = taskLabel(task.kind)
  const exec = task.execution
  const secondary =
    exec?.execution_mode === 'direct'
      ? ' · 直接模式'
      : exec?.execution_mode === 'interactive_bridge'
        ? ' · 交互桥'
        : ''
  switch (task.status) {
    case 'pending':
      return { label, stateText: '正在准备…', primaryAction: 'return', primaryLabel: '返回任务', canCancel: true }
    case 'running':
      return { label, stateText: `后台 AI 正在执行${secondary}`, primaryAction: 'return', primaryLabel: '返回任务', canCancel: true }
    case 'waiting_author': {
      const phase = task.kind === 'story_write' ? task.phase : null
      return {
        label,
        stateText: task.message ?? waitingAuthorMessage(task.kind, phase),
        primaryAction: 'gowrite',
        primaryLabel: '前往 Qoder 执行 /gowrite',
        canCancel: true,
      }
    }
    case 'confirming':
      return { label, stateText: '正在确认…', primaryAction: 'return', primaryLabel: '返回任务', canCancel: false }
    case 'candidate':
      return { label, stateText: candidateReadyMessage(task.kind), primaryAction: 'return', primaryLabel: '返回查看', canCancel: true }
    case 'failed':
      return { label, stateText: task.error ?? '任务失败', primaryAction: 'return', primaryLabel: '返回查看', canCancel: true }
    case 'canceled':
      return { label, stateText: '已取消', primaryAction: 'return', primaryLabel: '返回任务', canCancel: false }
  }
}

/** 任务是否仍然"活跃"（存在时阻止启动第二个任务；failed 可被替换重试）。 */
export function isTaskActive(status: AuthorTaskStatus): boolean {
  return status === 'pending' || status === 'running' || status === 'waiting_author' || status === 'candidate' || status === 'confirming'
}

/** 审计事件身份 key：event_id 优先，旧版回退 seq（展示 key 用，非去重逻辑）。 */
export function auditEventKey(event: { event_id?: string | null; seq: number }): string {
  return event.event_id && event.event_id.trim() ? event.event_id : `seq:${event.seq}`
}
