import type { ProjectDataEntry } from '../../bridge/client'

export interface AuthorField {
  key: string
  label: string
  value: string
}

const HIDDEN_FIELDS = new Set([
  'id', 'name', 'label', 'source_ref', 'source_kind', 'material_state', 'model_rev',
  'state_rev', 'schema_version', 'project_id', 'request_id', 'planning_token',
  'writing_token', 'scene_ref', 'authority', 'provenance', 'planning_source_ref',
  'source_state_ref', 'supersedes_state_ref', 'settlement_provenance', 'tombstoned',
  'content_sha256', 'source', 'target', 'source_name', 'target_name', 'relationship',
  'targets', 'characters', 'between', 'participants', 'from', 'to',
])

export const AUTHOR_FIELD_LABELS: Record<string, string> = {
  description: '描述', summary: '概述', role: '角色定位', identity: '身份', goal: '目标',
  motivation: '动机', personality: '性格', background: '背景', appearance: '外貌',
  ability: '能力', arc: '人物弧光', status: '当前状态', fact: '事实', content: '内容',
  note: '备注', notes: '备注', event: '事件', text: '内容', time: '时间',
  time_anchor: '时间锚点', story_time: '故事时间', when: '时间', date: '日期',
  temporal_anchor: '时间锚点', aliases: '别名', one_line_intro: '一句话介绍',
  role_identity: '身份 / 角色', position_title: '职位', faction_org: '阵营 / 组织',
  visible_traits: '特征', persona_core: '人设', goal_desire: '目标 / 欲望',
  fear_weakness: '恐惧 / 弱点', inner_conflict: '内在冲突', values_beliefs: '价值 / 信念',
  background_summary: '背景', speech_style: '说话特点', behavior_anchors: '行为特点',
  secrets: '秘密', current_state: '当前状态', current_objective: '当前目标',
  arc_stage: '人物弧阶段', relationship_phase: '关系阶段', key_history: '关键经历',
  current_tension: '当前张力', hidden_information: '隐瞒的信息', trust: '信任',
  closeness: '亲近', power_rank: '武力 / 等级', profession_rank: '职业 / 职级',
  current_location: '当前位置', current_level: '当前体系等级', system_level: '当前体系等级',
  state: '状态',
}

export const CHARACTER_FIELD_ORDER = [
  'one_line_intro', 'visible_traits', 'persona_core', 'role_identity', 'position_title',
  'background_summary', 'power_rank', 'profession_rank', 'current_level', 'system_level',
  'current_state', 'current_objective', 'arc_stage', 'speech_style', 'behavior_anchors',
  'goal_desire', 'fear_weakness', 'inner_conflict', 'faction_org', 'secrets', 'notes',
]

export function isInternalAuthorField(key: string): boolean {
  const lowered = key.toLowerCase()
  return HIDDEN_FIELDS.has(key)
    || lowered.endsWith('_rev')
    || lowered.endsWith('_hash')
    || lowered.endsWith('_token')
    || lowered.endsWith('_ref')
    || lowered.includes('fingerprint')
}

function formattedValue(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() || null
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) {
    const values = value.filter((item): item is string | number | boolean => (
      typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean'
    )).map(String).filter(Boolean)
    return values.length ? values.join('、') : null
  }
  return null
}

export function describeAuthorRecord(entry: ProjectDataEntry): AuthorField[] {
  if (!entry.record || typeof entry.record !== 'object' || Array.isArray(entry.record)) return []
  const fields = Object.entries(entry.record as Record<string, unknown>)
    .filter(([key]) => !isInternalAuthorField(key))
    .map(([key, value]) => ({ key, label: AUTHOR_FIELD_LABELS[key] ?? key, value: formattedValue(value) }))
    .filter((field): field is AuthorField => field.value !== null)
  const order = new Map(CHARACTER_FIELD_ORDER.map((key, index) => [key, index]))
  return fields.sort((left, right) => (
    (order.get(left.key) ?? 10_000) - (order.get(right.key) ?? 10_000)
    || left.label.localeCompare(right.label, 'zh-CN')
  ))
}

export function authorStatusLabel(status: 'current' | 'future' | undefined): '当前' | '规划中' {
  return status === 'future' ? '规划中' : '当前'
}

export function authorSourceLabel(sourceKind: string | null | undefined): string {
  if (sourceKind === 'production_story_state') return '来自已采用正文'
  if (sourceKind === 'approved_plan') return '来自已确认规划'
  if (sourceKind === 'author_workspace' || sourceKind === 'author_workspace_relationship') return '作者设定'
  return '作品资料'
}

function recordOf(entry: ProjectDataEntry): Record<string, unknown> {
  return entry.record && typeof entry.record === 'object' && !Array.isArray(entry.record)
    ? entry.record as Record<string, unknown>
    : {}
}

export function deterministicAvatar(entry: ProjectDataEntry): { text: string; hue: number } {
  const identity = String(entry.source_ref || entry.id || entry.label || '？')
  let hash = 0
  for (let index = 0; index < identity.length; index += 1) hash = ((hash * 31) + identity.charCodeAt(index)) >>> 0
  const label = entry.label.trim()
  return { text: label ? label.slice(0, 1).toUpperCase() : '？', hue: hash % 360 }
}

export function compactCharacter(entry: ProjectDataEntry) {
  const record = recordOf(entry)
  const text = (key: string) => typeof record[key] === 'string' ? String(record[key]).trim() : ''
  const role = text('role_identity') || text('position_title') || text('role') || text('identity')
  const details = describeAuthorRecord(entry)
  const hoverKeys = new Set(['visible_traits', 'current_state', 'current_objective', 'arc_stage'])
  return {
    avatar: deterministicAvatar(entry),
    name: entry.label || '（未命名人物）',
    intro: text('one_line_intro') || text('description') || '',
    role,
    details,
    hoverFields: details.filter((field) => hoverKeys.has(field.key)).slice(0, 4),
  }
}
