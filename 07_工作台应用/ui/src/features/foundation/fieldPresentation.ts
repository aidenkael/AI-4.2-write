/**
 * Small, explicit presentation metadata for the existing Foundation fields.
 *
 * This is deliberately not a property/schema engine: categories and fields are
 * finite UI choices backed by the current ProjectModel contract. Storage stays
 * in ProjectModel and unknown/custom values are preserved by the shared editor.
 */

export type FoundationFieldSection = 'core' | 'advanced'
export type FoundationFieldInput = 'text' | 'textarea' | 'select'

export interface FoundationFieldPresentation {
  key: string
  label: string
  section: FoundationFieldSection
  input: FoundationFieldInput
  rows?: number
  options?: readonly { value: string; label: string }[]
}

const text = (key: string, label: string, section: FoundationFieldSection = 'advanced'): FoundationFieldPresentation => (
  { key, label, section, input: 'text' }
)
const area = (key: string, label: string, section: FoundationFieldSection = 'advanced', rows = 2): FoundationFieldPresentation => (
  { key, label, section, input: 'textarea', rows }
)

const foreshadowingStates = [
  { value: 'planned', label: '计划中' },
  { value: 'planted', label: '已埋设' },
  { value: 'open', label: '开放中' },
  { value: 'paid_off', label: '已回收' },
  { value: 'resolved', label: '已解决' },
  { value: 'retired', label: '已退役' },
  { value: 'abandoned', label: '已放弃' },
] as const

export const FOUNDATION_FIELD_PRESENTATION: Record<string, readonly FoundationFieldPresentation[]> = {
  character: [
    area('one_line_intro', '一句话介绍', 'core'),
    text('role_identity', '角色 / 身份', 'core'),
    area('goal_desire', '目标 / 渴望', 'core'),
    text('aliases', '别名'), text('position_title', '职位'), area('visible_traits', '可见特征'),
    area('persona_core', '人设核心'), area('fear_weakness', '恐惧 / 弱点'), area('inner_conflict', '内在冲突'),
    area('values_beliefs', '价值 / 信念'), area('background_summary', '背景摘要', 'advanced', 3),
    area('speech_style', '说话特点'), area('behavior_anchors', '行为锚点'), area('secrets', '秘密'),
    area('current_state', '当前状态'), area('current_objective', '当前目标'), text('arc_stage', '人物弧阶段'),
    text('power_rank', '武力 / 等级'), text('current_level', '当前体系等级'), area('notes', '备注', 'advanced', 3),
  ],
  relationship: [
    area('description', '描述', 'core', 3), area('current_state', '当前关系状态', 'core'),
    text('relationship_phase', '关系阶段'), area('key_history', '关键经历', 'advanced', 3),
    area('current_tension', '当前张力'), area('hidden_information', '隐瞒的信息'),
    text('trust', '信任（可选）'), text('closeness', '亲近（可选）'), area('notes', '备注', 'advanced', 3),
  ],
  world_setting: [
    area('era_time_background', '时代 / 时间背景', 'core'), area('geographic_scope', '地理范围', 'core'),
    area('story_constraints', '故事约束', 'core'), area('hard_rules', '硬规则', 'core'),
    area('social_structure', '社会结构'), area('political_order', '政治秩序'), area('economy_resources', '经济 / 资源'),
    area('culture_customs', '文化 / 习俗'), area('technology_level', '科技水平'),
    area('supernatural_baseline', '超自然基线'), area('important_history', '重要历史'),
    area('prohibitions_taboos', '禁忌'), area('known_exceptions', '已知例外'), area('notes', '备注', 'advanced', 3),
  ],
  location: [
    text('type', '类型', 'core'), area('story_social_function', '故事 / 社会功能', 'core'),
    text('region_parent', '区域 / 上级'), area('physical_features', '物理特征'),
    text('controlling_organization', '控制组织'), area('rules_risks', '规则 / 风险'), area('current_state', '当前状态'),
  ],
  organization_force: [
    text('type', '类型', 'core'), area('purpose', '目的', 'core'),
    area('hierarchy', '层级'), area('leader_key_members', '领导 / 关键成员'), area('resources', '资源'),
    area('territory_scope', '范围'), area('rules', '规则'), area('external_relationships', '外部关系'), area('current_state', '当前状态'),
  ],
  system: [
    text('type', '类型', 'core'), area('purpose', '用途', 'core'), area('levels_stages', '等级 / 阶段', 'core', 3),
    area('entry_progression_requirements', '进入 / 晋升条件'), area('abilities_privileges', '能力 / 权利'),
    area('limitations_costs', '限制 / 代价'), area('visible_markers', '外显标志'), area('exceptions', '例外'),
    area('important_rules', '重要规则'), area('notes', '备注', 'advanced', 3),
  ],
  story_line: [
    area('goal_purpose', '目标 / 用途', 'core'), area('main_conflict', '主要冲突', 'core'), area('stakes', '代价', 'core'),
    area('stage_progress', '阶段 / 进度'), area('dependencies', '依赖'),
    area('expected_payoff_end_condition', '预期回收 / 结束条件'), area('notes', '备注', 'advanced', 3),
  ],
  promise_foreshadowing: [
    area('setup_trigger', '埋设 / 触发', 'core'), area('reader_question_promise', '读者问题 / 承诺', 'core'),
    { key: 'state', label: '状态', section: 'core', input: 'select', options: foreshadowingStates },
    area('intended_payoff', '计划回收'), area('actual_payoff', '实际回收'), area('notes', '备注', 'advanced', 3),
  ],
  mystery_information: [
    area('secret_fact', '秘密 / 事实', 'core', 3),
    area('who_knows', '谁知道'), area('who_does_not_know', '谁不知道'), area('mistaken_beliefs', '错误认知'),
    text('reveal_status', '揭示状态'), area('planned_reveal', '计划揭示'), area('actual_reveal_event_chapter', '实际揭示事件 / 章节'),
  ],
}

export function fieldsForCategory(category: string): readonly FoundationFieldPresentation[] {
  return FOUNDATION_FIELD_PRESENTATION[category] ?? []
}

export function fieldTuplesForCategory(category: string): ReadonlyArray<readonly [string, string]> {
  return fieldsForCategory(category).map((field) => [field.key, field.label] as const)
}

export function sectionFields(category: string, section: FoundationFieldSection): FoundationFieldPresentation[] {
  return fieldsForCategory(category).filter((field) => field.section === section)
}

const meaningful = (value: unknown): boolean => {
  if (typeof value === 'string') return Boolean(value.trim())
  if (Array.isArray(value)) return value.length > 0
  return value !== null && value !== undefined && value !== false
}

export function advancedValueCount(
  category: string,
  values: Record<string, unknown>,
  custom: Array<{ key: string; value: string }>,
): number {
  const known = sectionFields(category, 'advanced').filter((field) => meaningful(values[field.key])).length
  const customCount = custom.filter((field) => field.key.trim() && field.value.trim()).length
  return known + customCount
}

const OPTIONAL_SECTION_MODULES: Record<string, readonly string[]> = {
  systems: ['power_progression', 'career_rank', 'economy_resources', 'technology', 'supernatural_rules', 'custom'],
  mystery_information: ['mystery_information'],
}

/** Optional empty areas stay reachable but do not dominate the primary navigation. */
export function primaryFoundationSections(
  activeModules: readonly string[],
  recordCounts: Record<string, number>,
): { primary: string[]; optional: string[] } {
  const all = ['characters', 'relationships', 'canon_facts', 'locations', 'organizations', 'systems', 'storylines', 'foreshadowing', 'mystery_information']
  const active = new Set(activeModules)
  const optional: string[] = []
  const primary = all.filter((section) => {
    const modules = OPTIONAL_SECTION_MODULES[section]
    if (!modules) return true
    const visible = (recordCounts[section] ?? 0) > 0 || modules.some((module) => active.has(module))
    if (!visible) optional.push(section)
    return visible
  })
  return { primary, optional }
}
