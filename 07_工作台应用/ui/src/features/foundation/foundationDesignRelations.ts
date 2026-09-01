/**
 * 完善作品地基候选中“建议的跨元素关联”的纯函数投影层（可独立测试）。
 *
 * 合同：
 * - 行文本只用作者可读标题（候选键映射的标题 / 既有记录标签），
 *   绝不暴露 candidate_key / ref / relation_kind 等内部身份；
 * - 端点标题不可解析时如实返回 null（UI 显示“端点不明确”，绝不猜测）；
 * - 确认载荷只包含作者选中的关系，字段只保留 key/ref 身份。
 */
import type { FoundationDesignDomainRelation, ProjectData } from '../../bridge/client'

export const RELATION_KIND_LABELS: Record<string, string> = {
  character_affiliated_with_organization: '所属组织',
  character_uses_system: '关联体系',
  storyline_involves_character: '涉及人物',
  storyline_involves_organization: '涉及组织',
  storyline_involves_location: '涉及地点',
  foreshadowing_related_to: '相关对象',
  mystery_information_related_to: '相关对象',
}

export interface FdRelationRow {
  index: number
  relation: FoundationDesignDomainRelation
  sourceTitle: string | null
  targetTitle: string | null
  relationLabel: string
}

/** 候选提案内全部 candidate_key → 标题 映射（含关系条目的端点键所在集合）。 */
export function fdKeyTitles(proposal: Record<string, unknown> | null | undefined): Map<string, string> {
  const titles = new Map<string, string>()
  if (!proposal || typeof proposal !== 'object') return titles
  const collections = [
    'characters', 'relationships', 'world_settings', 'locations', 'organizations',
    'systems', 'story_lines', 'promise_foreshadowing', 'mystery_information',
  ]
  for (const key of collections) {
    const list = (proposal as Record<string, unknown>)[key]
    if (!Array.isArray(list)) continue
    for (const item of list) {
      if (!item || typeof item !== 'object') continue
      const record = item as Record<string, unknown>
      const candidateKey = typeof record.candidate_key === 'string' ? record.candidate_key : ''
      const title = typeof record.title === 'string' ? record.title
        : typeof record.label === 'string' ? record.label : ''
      if (candidateKey && title) titles.set(candidateKey, title)
    }
  }
  const core = (proposal as Record<string, unknown>).core_conflict
  if (core && typeof core === 'object') {
    const record = core as Record<string, unknown>
    if (typeof record.candidate_key === 'string' && typeof record.title === 'string') {
      titles.set(record.candidate_key, record.title)
    }
  }
  return titles
}

/** 既有正式记录的 ref → 作者可读标签 映射（供显式 ref 端点显示）。 */
export function fdRefTitles(data: ProjectData | null): Map<string, string> {
  const titles = new Map<string, string>()
  if (!data) return titles
  for (const entries of Object.values(data.sections ?? {})) {
    if (!Array.isArray(entries)) continue
    for (const entry of entries) {
      const ref = entry.source_ref ?? entry.id
      if (ref && entry.label) titles.set(ref, entry.label)
    }
  }
  return titles
}

function endpointTitle(
  key: string | null | undefined,
  ref: string | null | undefined,
  keyTitles: Map<string, string>,
  refTitles: Map<string, string>,
): string | null {
  if (key && keyTitles.has(key)) return keyTitles.get(key) ?? null
  if (ref && refTitles.has(ref)) return refTitles.get(ref) ?? null
  return null
}

/** 候选 domain_relations → 作者可读行模型；端点不可解析时标题为 null（不猜）。 */
export function fdRelationRows(
  relations: FoundationDesignDomainRelation[] | null | undefined,
  keyTitles: Map<string, string>,
  refTitles: Map<string, string>,
): FdRelationRow[] {
  if (!Array.isArray(relations)) return []
  return relations.map((relation, index) => ({
    index,
    relation,
    sourceTitle: endpointTitle(relation.source_key, relation.source_ref, keyTitles, refTitles),
    targetTitle: endpointTitle(relation.target_key, relation.target_ref, keyTitles, refTitles),
    relationLabel: RELATION_KIND_LABELS[relation.relation_kind] ?? '关联',
  }))
}

/** 行展示文本：端点不明确时返回 null（UI 如实提示；绝不暴露 key/ref/kind）。 */
export function fdRelationRowText(row: FdRelationRow): string | null {
  if (!row.sourceTitle || !row.targetTitle) return null
  return `${row.sourceTitle} — ${row.relationLabel} → ${row.targetTitle}`
}

export interface FdRelationSelection {
  include: boolean
  row: FdRelationRow
}

/** 确认载荷：只包含作者选中的关系；仅保留 key/ref 身份（候选键不持久化）。 */
export function fdSelectedRelationPayload(
  selections: FdRelationSelection[],
): FoundationDesignDomainRelation[] {
  return selections
    .filter((selection) => selection.include)
    .map(({ row }) => {
      const payload: FoundationDesignDomainRelation = { relation_kind: row.relation.relation_kind }
      if (row.relation.source_key) payload.source_key = row.relation.source_key
      if (row.relation.source_ref) payload.source_ref = row.relation.source_ref
      if (row.relation.target_key) payload.target_key = row.relation.target_key
      if (row.relation.target_ref) payload.target_ref = row.relation.target_ref
      return payload
    })
}
