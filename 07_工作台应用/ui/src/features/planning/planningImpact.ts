/**
 * 规划影响候选的作者呈现纯模型（无 React / DOM 依赖，可被 node:test 直接测试）。
 *
 * 约束：
 * - 候选只是“可能受影响”的提示，不是规划权威；
 * - 作者可见文本绝不暴露 raw ref / 内部 id（candidate_id 只进 payload，不进标签）；
 * - 「暂时保留」只映射状态转换，绝不触发任何生成。
 */

export type ImpactStatus = 'pending_author' | 'deferred' | 'in_replan' | 'resolved' | 'obsolete'

export interface ImpactCandidateView {
  candidateId: string
  summary: string
  status: ImpactStatus
  affectedChapterNumbers: number[]
  stageRefs: string[]
}

/** 概览/规划页需要作者处置的候选：待处理 + 已暂缓 + 重规划中。 */
export const ACTIVE_IMPACT_STATUSES: ImpactStatus[] = ['pending_author', 'deferred', 'in_replan']

function asImpactStatus(value: unknown): ImpactStatus | null {
  return typeof value === 'string' && (ACTIVE_IMPACT_STATUSES.includes(value as ImpactStatus) || value === 'resolved' || value === 'obsolete')
    ? (value as ImpactStatus)
    : null
}

export function unresolvedImpactCandidates(raw: Array<Record<string, unknown>> | null | undefined): ImpactCandidateView[] {
  if (!Array.isArray(raw)) return []
  const views: ImpactCandidateView[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const candidateId = item.candidate_id
    const summary = item.summary
    const status = asImpactStatus(item.status ?? 'pending_author')
    if (typeof candidateId !== 'string' || !candidateId) continue
    if (typeof summary !== 'string' || !summary.trim()) continue
    if (status === null || !ACTIVE_IMPACT_STATUSES.includes(status)) continue
    const chapters = Array.isArray(item.affected_chapter_numbers)
      ? item.affected_chapter_numbers.filter((n): n is number => typeof n === 'number' && Number.isInteger(n) && n > 0)
      : []
    const stageRefs = Array.isArray(item.affected_stage_refs)
      ? item.affected_stage_refs.filter((r): r is string => typeof r === 'string' && r.length > 0)
      : []
    views.push({
      candidateId,
      summary: summary.trim(),
      status,
      affectedChapterNumbers: [...new Set(chapters)].sort((a, b) => a - b),
      stageRefs: [...new Set(stageRefs)],
    })
  }
  return views.sort((a, b) => a.candidateId.localeCompare(b.candidateId))
}

/** 概览紧凑提示：只给计数，不铺明细。 */
export function impactNoticeText(pendingCount: number): string | null {
  if (!Number.isInteger(pendingCount) || pendingCount <= 0) return null
  return `有 ${pendingCount} 项作者修改可能影响后续规划`
}

/** 章节号 → 作者可读范围：连续段合并为「第 48–53 章」，其余顿号分隔。 */
export function formatAffectedChapters(numbers: number[]): string | null {
  if (!numbers.length) return null
  const sorted = [...new Set(numbers)].sort((a, b) => a - b)
  const parts: string[] = []
  let start = sorted[0]
  let end = sorted[0]
  const flush = () => {
    parts.push(start === end ? `第 ${start} 章` : `第 ${start}–${end} 章`)
  }
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i] === end + 1) {
      end = sorted[i]
      continue
    }
    flush()
    start = sorted[i]
    end = sorted[i]
  }
  flush()
  return parts.join('、')
}

export interface StageTitleSource {
  ref?: string | null
  title?: string | null
}

/** 阶段 ref → 作者可读标题；无法解析的绝不显示原始 ref。 */
export function resolveStageTitles(stageRefs: string[], stages: StageTitleSource[] | null | undefined): string[] {
  if (!stageRefs.length || !Array.isArray(stages)) return []
  const byRef = new Map<string, string>()
  for (const stage of stages) {
    if (typeof stage.ref === 'string' && stage.ref && typeof stage.title === 'string' && stage.title.trim()) {
      byRef.set(stage.ref, stage.title.trim())
    }
  }
  return stageRefs.map((ref) => byRef.get(ref)).filter((title): title is string => Boolean(title))
}

/** 一行候选的作者可读文本：摘要 + 影响范围；绝不包含 raw ref。 */
export function impactRowText(view: ImpactCandidateView, stages: StageTitleSource[] | null | undefined): string {
  const scopes: string[] = []
  const chapters = formatAffectedChapters(view.affectedChapterNumbers)
  if (chapters) scopes.push(chapters)
  const stageTitles = resolveStageTitles(view.stageRefs, stages)
  if (stageTitles.length) scopes.push(stageTitles.map((title) => `阶段「${title}」`).join('、'))
  if (!scopes.length) return view.summary
  return `${view.summary}（可能影响 ${scopes.join(' 与 ')}）`
}

/** 「重新规划受影响内容」的精确 payload：只带选中的候选 id。 */
export function impactReplanPayload(
  projectId: string,
  candidateIds: string[],
): { project_id: string; author_question: string; planning_mode: 'impact_replan'; impact_candidate_ids: string[] } {
  return {
    project_id: projectId,
    author_question: '',
    planning_mode: 'impact_replan',
    impact_candidate_ids: candidateIds.filter((id) => typeof id === 'string' && id.length > 0),
  }
}

/** 「暂时保留」：只做状态转换映射；不是生成请求，也没有 planning_mode。 */
export function deferCandidatePayload(
  projectId: string,
  candidateId: string,
): { project_id: string; candidate_id: string; status: 'deferred' } {
  return { project_id: projectId, candidate_id: candidateId, status: 'deferred' }
}

/** 暂缓后恢复待处理。 */
export function restoreCandidatePayload(
  projectId: string,
  candidateId: string,
): { project_id: string; candidate_id: string; status: 'pending_author' } {
  return { project_id: projectId, candidate_id: candidateId, status: 'pending_author' }
}
