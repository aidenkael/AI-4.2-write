/**
 * 分层长篇规划入口纯模型（无 React / DOM 依赖，可被 node:test 直接测试）。
 *
 * 约束：
 * - 模式是同一 StoryPlan 操作的结构化范围，不是多个后端；
 * - 卷/阶段选择只用稳定 ref，绝不按标题推断；
 * - 近期细化范围必须显式、有界、作者可见。
 */

export type PlanningMode = 'free' | 'book' | 'stage' | 'near_term' | 'impact_replan'

export const PLANNING_MODES: PlanningMode[] = ['free', 'book', 'stage', 'near_term', 'impact_replan']

export const NEAR_TERM_MAX_SPAN = 12
export const NEAR_TERM_DEFAULT_SPAN = 5

export interface StageOption {
  ref: string
  title: string
}

/** 从 length_plan.stages 提取稳定 ref 选项；非法条目绝不进入选择器。 */
export function stageOptionsFromLengthPlan(stages: Array<Record<string, unknown>> | null | undefined): StageOption[] {
  if (!Array.isArray(stages)) return []
  const options: StageOption[] = []
  for (const stage of stages) {
    const ref = stage?.ref
    const title = stage?.title
    if (typeof ref !== 'string' || !ref) continue
    options.push({ ref, title: typeof title === 'string' && title.trim() ? title.trim() : '（未命名阶段）' })
  }
  return options
}

/** 近期细化的默认范围：从当前章开始的一小段（作者总是可以再改）。 */
export function defaultNearTermRange(currentChapter: number): [number, number] {
  const start = Number.isInteger(currentChapter) && currentChapter > 0 ? currentChapter : 1
  return [start, start + NEAR_TERM_DEFAULT_SPAN - 1]
}

/** 范围校验：返回作者可读错误文本；合法时返回 null。 */
export function validateNearTermRange(start: number, end: number): string | null {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < 1) {
    return '章节号必须是正整数。'
  }
  if (end < start) return '结束章不能早于起始章。'
  if (end - start + 1 > NEAR_TERM_MAX_SPAN) {
    return `单次细化范围不得超过 ${NEAR_TERM_MAX_SPAN} 章，请缩小范围。`
  }
  return null
}

export interface PlanningActionOptions {
  mode: PlanningMode
  authorQuestion?: string
  stageRef?: string
  chapterRange?: [number, number]
  impactCandidateIds?: string[]
}

export interface PlanningActionPayload {
  project_id: string
  author_question: string
  planning_mode: PlanningMode
  stage_ref?: string
  chapter_range?: [number, number]
  impact_candidate_ids?: string[]
}

/** 构造结构化规划动作 payload；非法输入返回错误文本而不是猜测范围。 */
export function planningActionPayload(
  projectId: string,
  options: PlanningActionOptions,
): { payload: PlanningActionPayload | null; error: string | null } {
  if (!projectId) return { payload: null, error: '请先选择正式作品。' }
  if (!PLANNING_MODES.includes(options.mode)) return { payload: null, error: '不支持的规划模式。' }
  const base: PlanningActionPayload = {
    project_id: projectId,
    author_question: (options.authorQuestion ?? '').trim(),
    planning_mode: options.mode,
  }
  if (options.mode === 'stage') {
    if (!options.stageRef) return { payload: null, error: '请先选择一个真实的卷/阶段。' }
    base.stage_ref = options.stageRef
  }
  if (options.mode === 'near_term') {
    const range = options.chapterRange
    if (!range) return { payload: null, error: '请先给出近期细化的章节范围。' }
    const invalid = validateNearTermRange(range[0], range[1])
    if (invalid) return { payload: null, error: invalid }
    base.chapter_range = [range[0], range[1]]
  }
  if (options.mode === 'impact_replan') {
    const ids = (options.impactCandidateIds ?? []).filter((id) => typeof id === 'string' && id.length > 0)
    if (!ids.length) return { payload: null, error: '重新规划受影响内容必须选择至少一个影响候选。' }
    base.impact_candidate_ids = ids
  }
  return { payload: base, error: null }
}
