/**
 * 显式领域关系选择器的纯函数层（可独立测试；无 DOM / 无 Bridge 调用）。
 *
 * 合同：
 * - 关系类型与后端 project_model 的中央领域关系规格一一对应，不预建通用本体；
 * - 选项只来自真实 ProjectData 分区；内部存稳定 ref，可见文本永远是标签；
 * - 遗留纯文本关联只做“唯一精确标题”预填；歧义/未匹配保持作者可读提示，绝不猜测。
 */
import type { ExplicitDependency, ProjectData } from '../../bridge/client'

/** 作者可选择的关联目标（ref 仅内部使用，绝不作为普通可见标签渲染）。 */
export interface RelationOption {
  ref: string
  label: string
  category: string
  status: 'current' | 'future'
}

export interface RelationSpec {
  relation_kind: string
  label: string
  targetCategories: string[]
}

/** 与后端 _DOMAIN_RELATION_SPECS 对应的 UI 元数据（按源记录分类组织）。 */
export const RELATION_SPECS_BY_SOURCE_CATEGORY: Record<string, RelationSpec[]> = {
  character: [
    { relation_kind: 'character_affiliated_with_organization', label: '所属组织', targetCategories: ['organization_force'] },
    { relation_kind: 'character_uses_system', label: '相关体系', targetCategories: ['system'] },
  ],
  story_line: [
    { relation_kind: 'storyline_involves_character', label: '参与人物', targetCategories: ['character'] },
    { relation_kind: 'storyline_involves_organization', label: '相关组织', targetCategories: ['organization_force'] },
    { relation_kind: 'storyline_involves_location', label: '相关地点', targetCategories: ['location'] },
  ],
  promise_foreshadowing: [
    {
      relation_kind: 'foreshadowing_related_to', label: '相关对象',
      targetCategories: ['character', 'world_setting', 'location', 'organization_force', 'system', 'story_line'],
    },
  ],
  mystery_information: [
    {
      relation_kind: 'mystery_information_related_to', label: '相关对象',
      targetCategories: ['character', 'world_setting', 'location', 'organization_force', 'system', 'story_line'],
    },
  ],
}

/** 领域分类 → ProjectData 分区。 */
export const SECTION_BY_CATEGORY: Record<string, keyof ProjectData['sections']> = {
  character: 'characters',
  world_setting: 'canon_facts',
  location: 'locations',
  organization_force: 'organizations',
  system: 'systems',
  story_line: 'storylines',
}

/** 普通可见 UI 的展示标签：只返回作者可读名称，绝不返回 ref。 */
export function displayLabel(option: RelationOption): string {
  return option.label.trim() || '（未命名记录）'
}

/** 从真实 ProjectData 分区收集可选关联目标；不构造假条目。 */
export function relationOptions(data: ProjectData | null, categories: string[]): RelationOption[] {
  if (!data) return []
  const options: RelationOption[] = []
  const seen = new Set<string>()
  for (const category of categories) {
    const section = SECTION_BY_CATEGORY[category]
    if (!section) continue
    for (const entry of data.sections[section] ?? []) {
      const ref = entry.source_ref ?? entry.id
      if (!ref || seen.has(ref)) continue
      seen.add(ref)
      options.push({
        ref,
        label: entry.label || '（未命名记录）',
        category,
        status: entry.status === 'future' ? 'future' : 'current',
      })
    }
  }
  return options
}

/** 某源记录当前已存在的某类领域关系目标 refs（来自同一快照的派生事实）。 */
export function existingRelationTargets(
  dependencies: ExplicitDependency[] | undefined,
  sourceRef: string | null | undefined,
  relationKind: string,
): string[] {
  if (!sourceRef || !Array.isArray(dependencies)) return []
  return dependencies
    .filter((edge) => edge.source_ref === sourceRef && edge.relation_kind === relationKind)
    .map((edge) => edge.target_ref)
}

/** 遗留纯文本关联字段 → 去空白名称列表（字符串或字符串数组）。 */
export function legacyTitles(value: unknown): string[] {
  if (typeof value === 'string') {
    return value.split(/[、,，\n;；]/).map((item) => item.trim()).filter(Boolean)
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? '').trim()).filter(Boolean)
  }
  return []
}

export interface LegacyResolution {
  /** 已唯一精确解析并建议预选的目标 refs（按输入标题顺序）。 */
  refs: string[]
  /** 歧义或未匹配的遗留标题（保持作者可读提示，绝不静默转换）。 */
  unresolved: string[]
}

/**
 * 遗留文本的安全解析：只有当每个名称在候选中精确且唯一匹配时才预选；
 * 无模糊匹配、无推断；歧义/未匹配进入 unresolved。
 */
export function resolveLegacyTitles(titles: string[], options: RelationOption[]): LegacyResolution {
  const refs: string[] = []
  const unresolved: string[] = []
  const chosen = new Set<string>()
  for (const title of titles) {
    const matches = options.filter((option) => option.label === title)
    if (matches.length === 1 && !chosen.has(matches[0].ref)) {
      chosen.add(matches[0].ref)
      refs.push(matches[0].ref)
    } else {
      unresolved.push(title)
    }
  }
  return { refs, unresolved }
}

/** 作者已保存规范化选择后，停止写回重复的遗留关系文本字段（不触碰其他数据）。 */
export function stripLegacyRelationFields(
  data: Record<string, unknown>,
  legacyFields: string[],
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...data }
  for (const field of legacyFields) delete next[field]
  return next
}

/** 组装提交后端的完整受管关系集合（只含给定类型的选择）。 */
export function relationSelections(
  selections: Record<string, string[]>,
): Array<{ relation_kind: string; target_ref: string }> {
  const result: Array<{ relation_kind: string; target_ref: string }> = []
  for (const [relationKind, targets] of Object.entries(selections)) {
    for (const targetRef of targets) {
      result.push({ relation_kind: relationKind, target_ref: targetRef })
    }
  }
  return result
}

// ---------------- 遗留纯文本关联字段的安全兼容 ----------------

export interface LegacyRelationConfig {
  field: string
  kinds: string[]
}

/** 被规范化领域关系取代的遗留文本字段（按源记录分类）。 */
export const LEGACY_RELATION_FIELDS_BY_CATEGORY: Record<string, LegacyRelationConfig[]> = {
  character: [{ field: 'faction_org', kinds: ['character_affiliated_with_organization'] }],
  story_line: [
    { field: 'participating_characters', kinds: ['storyline_involves_character'] },
    { field: 'related_organizations_locations', kinds: ['storyline_involves_organization', 'storyline_involves_location'] },
  ],
  promise_foreshadowing: [{ field: 'related_entities', kinds: ['foreshadowing_related_to'] }],
}

export const LEGACY_RELATION_FIELD_LABELS: Record<string, string> = {
  faction_org: '阵营 / 组织',
  participating_characters: '参与人物',
  related_organizations_locations: '相关组织 / 地点',
  related_entities: '相关对象',
}

/** 不应落入“自定义字段”编辑区的遗留关系文本字段集合。 */
export const LEGACY_RELATION_FIELD_KEYS = new Set(
  Object.values(LEGACY_RELATION_FIELDS_BY_CATEGORY).flat().map((item) => item.field),
)

export interface RelationInitialization {
  selections: Record<string, string[]>
  /** 作者可读的遗留提示（歧义/未匹配；绝不静默转换）。 */
  hints: Array<{ field: string; text: string }>
}

/**
 * 编辑器打开时的确定性初始化：
 * - 已有规范化关系 → 直接采用；
 * - 无规范化关系且遗留文本每个名称都能唯一精确匹配 → 建议预选；
 * - 其余情况：遗留文本保留为作者可读提示，绝不猜测。
 */
export function initializeRelationSelections(params: {
  category: string
  sourceRef: string | null | undefined
  record: Record<string, unknown>
  data: ProjectData | null
}): RelationInitialization {
  const specs = RELATION_SPECS_BY_SOURCE_CATEGORY[params.category] ?? []
  const selections: Record<string, string[]> = {}
  const hints: Array<{ field: string; text: string }> = []
  for (const spec of specs) {
    selections[spec.relation_kind] = existingRelationTargets(
      params.data?.explicit_dependencies, params.sourceRef, spec.relation_kind,
    )
  }
  if (!params.data) return { selections, hints }
  for (const legacy of LEGACY_RELATION_FIELDS_BY_CATEGORY[params.category] ?? []) {
    const titles = legacyTitles(params.record[legacy.field])
    if (!titles.length) continue
    const categories = new Set<string>()
    for (const kind of legacy.kinds) {
      specs.find((spec) => spec.relation_kind === kind)?.targetCategories.forEach((category) => categories.add(category))
    }
    const options = relationOptions(params.data, [...categories])
    const resolved = resolveLegacyTitles(titles, options)
    const hasCanonical = legacy.kinds.some((kind) => (selections[kind] ?? []).length > 0)
    if (!hasCanonical && resolved.refs.length && resolved.unresolved.length === 0) {
      const optionByRef = new Map(options.map((option) => [option.ref, option]))
      for (const ref of resolved.refs) {
        const option = optionByRef.get(ref)
        if (!option) continue
        const kind = legacy.kinds.find((candidate) => (
          specs.find((spec) => spec.relation_kind === candidate)?.targetCategories.includes(option.category)
        ))
        if (kind && !(selections[kind] ?? []).includes(ref)) {
          selections[kind] = [...(selections[kind] ?? []), ref]
        }
      }
    } else {
      hints.push({
        field: legacy.field,
        text: `遗留文本“${titles.join('、')}”未能唯一对应现有记录，已保留原文本；如需结构化请直接选择关联。`,
      })
    }
  }
  return { selections, hints }
}

/** 保存时：某遗留字段对应的任一类关系已有选择 → 停止写回重复的遗留文本字段。 */
export function legacyFieldsToStrip(
  category: string,
  selections: Record<string, string[]>,
): string[] {
  const stripped: string[] = []
  for (const legacy of LEGACY_RELATION_FIELDS_BY_CATEGORY[category] ?? []) {
    const selected = legacy.kinds.some((kind) => (selections[kind] ?? []).length > 0)
    if (selected) stripped.push(legacy.field)
  }
  return stripped
}
