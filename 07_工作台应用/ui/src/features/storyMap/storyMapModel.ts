/**
 * Story Map 统一定性投影层（派生视图唯一解析点）。
 *
 * 职责只有一件事：`权威 ProjectData 投影 → 安全的图/时间线/线索视图模型`。
 *
 * 合同（对应长期开发手册 8.3 D/C 与 AGENTS 六页合同）：
 * - 不推断故事事实：无模型调用、无启发式 NLP、无臆造节点/边/日期/时长；
 * - 人物节点只来自真实正式 character 记录；关系边只来自真实 relationship 记录，
 *   且两端必须能按显式存储字段（id/名称精确匹配）解析；
 * - 无法解析的关系记录进入 `unresolved` 紧凑区块，如实可见，不消失、不猜测；
 * - 时间视图只使用显式存储的时间锚点；没有锚点的事件保留真实叙事顺序并明确标注；
 * - 重复记录（同 id 或同渲染身份）只呈现一次；
 * - 本模块是纯函数：Foundation 与 Story Map 共用 `describeRecord` 的字段描述规则，
 *   不允许页面 JSX 各自发明解析规则。
 *
 * 派生 vs 权威边界：本层输出永远是只读视图模型；下一里程碑的作者编辑/语义结算
 * 只作用于权威 Story State，经安全合同写回后由本层重新投影。
 */
import type { ProjectData, ProjectDataEntry } from '../../bridge/client'

// ---------------- 通用记录描述（Foundation / StoryMap 共用） ----------------

export interface RecordField {
  key: string
  label: string
  value: string
}

// 常见正式字段的作者面标签；未收录的键按原样低调展示（真实数据，不翻译也不隐藏）。
const FIELD_LABELS: Record<string, string> = {
  name: '名称', label: '名称', description: '描述', summary: '概述',
  role: '角色定位', identity: '身份', goal: '目标', motivation: '动机',
  personality: '性格', background: '背景', appearance: '外貌', ability: '能力',
  arc: '人物弧光', status: '当前状态', relation: '关系', relationship: '关系',
  between: '双方', parties: '双方', targets: '双方', characters: '双方',
  fact: '事实', content: '内容', note: '备注', event: '事件', text: '内容',
  time: '时间', time_anchor: '时间锚点', story_time: '故事时间', when: '时间',
  date: '日期', temporal_anchor: '时间锚点',
}

/** 把一条正式记录投影为作者可读字段列表；跳过 id/authority/label 等机械键。 */
export function describeRecord(entry: ProjectDataEntry): RecordField[] {
  const record = entry.record
  if (!record || typeof record !== 'object' || Array.isArray(record)) return []
  const out: RecordField[] = []
  for (const [k, v] of Object.entries(record as Record<string, unknown>)) {
    if (k === 'id' || k === 'authority' || k === 'label' || k === 'name') continue
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      out.push({ key: k, label: FIELD_LABELS[k] ?? k, value: String(v) })
    } else if (Array.isArray(v)) {
      const text = v.filter((x) => typeof x === 'string').join('、')
      if (text) out.push({ key: k, label: FIELD_LABELS[k] ?? k, value: text })
    }
  }
  return out
}

// ---------------- 人物关系图 ----------------

export interface GraphNode {
  id: string
  label: string
  /** 图内短标签：name 优先，否则 label 截断（完整文本在详情面板查看，不臆造） */
  short: string
  fields: RecordField[]
}

export interface GraphEdge {
  id: string
  label: string
  source: string
  target: string
  fields: RecordField[]
}

export interface UnresolvedRelation {
  id: string
  label: string
  reason: string
}

export interface RelationshipGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  unresolved: UnresolvedRelation[]
}

// 仓库真实 Story State 合同支持的显式端点形状（集中于此，不散落页面）：
// - 数组形状：targets / characters / between / participants
// - 成对形状：source+target / from+to
const ARRAY_ENDPOINT_KEYS = ['targets', 'characters', 'between', 'participants'] as const
const PAIR_ENDPOINT_KEYS: ReadonlyArray<readonly [string, string]> = [
  ['source', 'target'],
  ['from', 'to'],
]

// 显式时间锚点键（仅当真实存储时采用）。
const TEMPORAL_KEYS = ['time', 'time_anchor', 'story_time', 'temporal_anchor', 'when', 'date'] as const

const isNonEmptyString = (v: unknown): v is string => typeof v === 'string' && v.trim().length > 0

function entryLabel(entry: ProjectDataEntry): string {
  return entry.label || entry.id || '（未命名条目）'
}

function rawEndpointText(value: unknown): string | null {
  if (isNonEmptyString(value)) return value.trim()
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const rec = value as Record<string, unknown>
    for (const key of ['id', 'name', 'label'] as const) {
      if (isNonEmptyString(rec[key])) return rec[key].trim()
    }
  }
  return null
}

function extractRawEndpoints(record: unknown): unknown[] | null {
  if (!record || typeof record !== 'object' || Array.isArray(record)) return null
  const rec = record as Record<string, unknown>
  for (const key of ARRAY_ENDPOINT_KEYS) {
    const v = rec[key]
    if (Array.isArray(v)) return v
  }
  for (const [a, b] of PAIR_ENDPOINT_KEYS) {
    if (rec[a] !== undefined || rec[b] !== undefined) return [rec[a], rec[b]]
  }
  return null
}

/** 权威 ProjectData → 只读关系图视图模型；绝不臆造节点或边。 */
export function projectRelationshipGraph(data: ProjectData | null): RelationshipGraph {
  const empty: RelationshipGraph = { nodes: [], edges: [], unresolved: [] }
  if (!data) return empty

  const nodes: GraphNode[] = []
  const idIndex = new Map<string, string>() // character id / name / label → node id
  data.sections.characters.forEach((entry, i) => {
    const nodeId = isNonEmptyString(entry.id) ? entry.id : `char:${i}`
    const label = entryLabel(entry)
    let name: string | null = null
    const record = entry.record
    if (record && typeof record === 'object' && !Array.isArray(record)) {
      const n = (record as Record<string, unknown>).name
      if (isNonEmptyString(n)) name = n.trim()
    }
    const short = name ?? (label.length > 12 ? `${label.slice(0, 12)}…` : label)
    nodes.push({ id: nodeId, label, short, fields: describeRecord(entry) })
    idIndex.set(nodeId, nodeId)
    if (isNonEmptyString(entry.label)) idIndex.set(entry.label.trim(), nodeId)
    if (name) idIndex.set(name, nodeId)
  })

  const edges: GraphEdge[] = []
  const unresolved: UnresolvedRelation[] = []
  const edgeIdentity = new Set<string>()
  const unresolvedIdentity = new Set<string>()

  const addUnresolved = (entry: ProjectDataEntry, reason: string) => {
    const key = `${entry.id ?? entry.label}::${reason}`
    if (unresolvedIdentity.has(key)) return
    unresolvedIdentity.add(key)
    unresolved.push({ id: entry.id ?? '', label: entryLabel(entry), reason })
  }

  for (const entry of data.sections.relationships) {
    const raw = extractRawEndpoints(entry.record)
    if (!raw) {
      addUnresolved(entry, '没有显式两端字段（targets/characters/between/source+target 等）')
      continue
    }
    const texts = raw.map(rawEndpointText)
    if (texts.some((t) => t === null)) {
      addUnresolved(entry, '端点不是可解析的 id/名称')
      continue
    }
    if (texts.length !== 2) {
      addUnresolved(entry, `显式端点数量为 ${texts.length}，无法形成单条连线`)
      continue
    }
    const source = idIndex.get(texts[0] as string) ?? null
    const target = idIndex.get(texts[1] as string) ?? null
    if (!source || !target) {
      addUnresolved(entry, '端点无法对应到已记录人物')
      continue
    }
    if (source === target) {
      addUnresolved(entry, '两端指向同一人物')
      continue
    }
    const label = entryLabel(entry)
    const identity = `${source}|${target}|${label}`
    if (edgeIdentity.has(identity)) continue // 重复记录只呈现一次
    edgeIdentity.add(identity)
    edges.push({
      id: isNonEmptyString(entry.id) ? entry.id : `rel:${edges.length}`,
      label,
      source,
      target,
      fields: describeRecord(entry),
    })
  }

  return { nodes, edges, unresolved }
}

// ---------------- 时间与事件 ----------------

export interface TimelineItem {
  id: string
  label: string
  /** 显式存储的时间锚点；null = 仅有叙事顺序，无精确时间。 */
  anchor: string | null
  /** 真实叙事顺序（数组下标），不是臆造时间。 */
  order: number
  fields: RecordField[]
}

export interface TimeEventModel {
  items: TimelineItem[]
  hasPreciseAnchors: boolean
}

/** 权威 occurred_events → 时间/事件视图模型；只用显式时间字段，否则保留顺序并标注。 */
export function projectTimeEvents(data: ProjectData | null): TimeEventModel {
  if (!data) return { items: [], hasPreciseAnchors: false }
  const items: TimelineItem[] = data.sections.occurred_events.map((entry, i) => {
    let anchor: string | null = null
    const record = entry.record
    if (record && typeof record === 'object' && !Array.isArray(record)) {
      const rec = record as Record<string, unknown>
      for (const key of TEMPORAL_KEYS) {
        const v = rec[key]
        if (isNonEmptyString(v)) {
          anchor = v.trim()
          break
        }
        if (typeof v === 'number') {
          anchor = String(v)
          break
        }
      }
    }
    return {
      id: isNonEmptyString(entry.id) ? entry.id : `event:${i}`,
      label: entryLabel(entry),
      anchor,
      order: i,
      fields: describeRecord(entry),
    }
  })
  return { items, hasPreciseAnchors: items.some((it) => it.anchor !== null) }
}

// ---------------- 未解决线索 ----------------

export interface ThreadItem {
  id: string
  label: string
  fields: RecordField[]
}

/** 权威 open_threads → 聚焦线索视图模型。 */
export function projectOpenThreads(data: ProjectData | null): ThreadItem[] {
  if (!data) return []
  return data.sections.open_threads.map((entry, i) => ({
    id: isNonEmptyString(entry.id) ? entry.id : `thread:${i}`,
    label: entryLabel(entry),
    fields: describeRecord(entry),
  }))
}
