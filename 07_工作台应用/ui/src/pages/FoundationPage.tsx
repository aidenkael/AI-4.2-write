import { Check, FileCheck2, GitBranch, MapPin, Pencil, Plus, Save, Sparkles, Trash2, UserRound, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { FoundationDesignItem, FoundationDesignResult, ProjectDataEntry } from '../bridge/client'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { useAuthorTask } from '../features/tasks/AuthorTaskCoordinator'
import { describeRecord } from '../features/storyMap/storyMapModel'
import { authorSourceLabel, authorStatusLabel, compactCharacter } from '../features/presentation/authorPresentation'
import { CharacterEditor, RelationshipEditor, recordObject, splitEditorData } from '../features/foundation/recordEditors'
import { RelationSelector } from '../features/foundation/RelationSelector'
import {
  initializeRelationSelections,
  legacyFieldsToStrip,
  relationOptions,
  relationSelections,
  stripLegacyRelationFields,
  RELATION_SPECS_BY_SOURCE_CATEGORY,
  type RelationSpec,
} from '../features/foundation/relationSelectors'

type FoundationTab =
  | 'characters' | 'relationships' | 'canon_facts' | 'locations' | 'organizations'
  | 'systems' | 'storylines' | 'foreshadowing' | 'mystery_information'
type MaterialState = 'current' | 'future'

const tabs: Array<{ key: FoundationTab; label: string; Icon: typeof UserRound; category: string }> = [
  { key: 'characters', label: '人物', Icon: UserRound, category: 'character' },
  { key: 'relationships', label: '关系', Icon: GitBranch, category: 'relationship' },
  { key: 'canon_facts', label: '世界', Icon: FileCheck2, category: 'world_setting' },
  { key: 'locations', label: '地点', Icon: MapPin, category: 'location' },
  { key: 'organizations', label: '组织', Icon: GitBranch, category: 'organization_force' },
  { key: 'systems', label: '系统', Icon: FileCheck2, category: 'system' },
  { key: 'storylines', label: '故事线', Icon: MapPin, category: 'story_line' },
  { key: 'foreshadowing', label: '伏笔与承诺', Icon: Check, category: 'promise_foreshadowing' },
  { key: 'mystery_information', label: '悬疑信息', Icon: Check, category: 'mystery_information' },
]

const tabGroups: Array<{ label: string; tabs: FoundationTab[] }> = [
  { label: '人物与关系', tabs: ['characters', 'relationships'] },
  { label: '世界与规则', tabs: ['canon_facts', 'locations', 'organizations', 'systems'] },
  { label: '故事线索', tabs: ['storylines', 'foreshadowing', 'mystery_information'] },
]

const groupForTab = (tab: FoundationTab) => tabGroups.find((group) => group.tabs.includes(tab)) ?? tabGroups[0]

const characterFields = [
  ['aliases', '别名'], ['one_line_intro', '一句话介绍'], ['role_identity', '角色 / 身份'],
  ['position_title', '职位'], ['visible_traits', '可见特征'],
  ['persona_core', '人设核心'], ['goal_desire', '目标 / 渴望'], ['fear_weakness', '恐惧 / 弱点'],
  ['inner_conflict', '内在冲突'], ['values_beliefs', '价值 / 信念'], ['background_summary', '背景摘要'],
  ['speech_style', '说话特点'], ['behavior_anchors', '行为锚点'], ['secrets', '秘密'],
  ['current_state', '当前状态'], ['current_objective', '当前目标'], ['arc_stage', '人物弧阶段'],
  ['notes', '备注'],
] as const
const fieldSets = {
  canon_facts: [
    ['era_time_background', '时代 / 时间背景'], ['geographic_scope', '地理范围'],
    ['social_structure', '社会结构'], ['political_order', '政治秩序'], ['economy_resources', '经济 / 资源'],
    ['culture_customs', '文化 / 习俗'], ['technology_level', '科技水平'],
    ['supernatural_baseline', '超自然基线'], ['important_history', '重要历史'],
    ['hard_rules', '硬规则'], ['prohibitions_taboos', '禁忌'], ['known_exceptions', '已知例外'],
    ['story_constraints', '故事约束'], ['notes', '备注'],
  ],
  locations: [
    ['type', '类型'], ['region_parent', '区域 / 上级'], ['physical_features', '物理特征'],
    ['story_social_function', '故事 / 社会功能'], ['controlling_organization', '控制组织'],
    ['rules_risks', '规则 / 风险'], ['current_state', '当前状态'],
  ],
  organizations: [
    ['type', '类型'], ['purpose', '目的'], ['hierarchy', '层级'],
    ['leader_key_members', '领导 / 关键成员'], ['resources', '资源'], ['territory_scope', '范围'],
    ['rules', '规则'], ['external_relationships', '外部关系'], ['current_state', '当前状态'],
  ],
  systems: [
    ['type', '类型'], ['purpose', '用途'], ['levels_stages', '等级 / 阶段'],
    ['entry_progression_requirements', '进入 / 晋升条件'], ['abilities_privileges', '能力 / 权利'],
    ['limitations_costs', '限制 / 代价'], ['visible_markers', '外显标志'],
    ['exceptions', '例外'], ['important_rules', '重要规则'], ['notes', '备注'],
  ],
  storylines: [
    ['goal_purpose', '目标 / 用途'], ['stakes', '代价'], ['main_conflict', '主要冲突'],
    ['stage_progress', '阶段 / 进度'], ['dependencies', '依赖'],
    ['expected_payoff_end_condition', '预期回收 / 结束条件'], ['notes', '备注'],
  ],
  foreshadowing: [
    ['setup_trigger', '埋设 / 触发'], ['reader_question_promise', '读者问题 / 承诺'],
    ['state', '状态'], ['intended_payoff', '计划回收'],
    ['actual_payoff', '实际回收'], ['notes', '备注'],
  ],
  mystery_information: [
    ['secret_fact', '秘密 / 事实'], ['who_knows', '谁知道'], ['who_does_not_know', '谁不知道'],
    ['mistaken_beliefs', '错误认知'], ['reveal_status', '揭示状态'],
    ['planned_reveal', '计划揭示'], ['actual_reveal_event_chapter', '实际揭示事件 / 章节'],
  ],
} as const
const fieldsForTab = (tab: FoundationTab) => tab === 'characters'
  ? characterFields
  : tab === 'relationships'
    ? []
    : fieldSets[tab]

interface RecordForm {
  mode: 'create' | 'edit'
  ref: string | null
  title: string
  material_state: MaterialState
  category: string
  data: Record<string, string>
  extraFields: Array<{ key: string; value: string; isList: boolean }>
  preservedData: Record<string, unknown>
  knownListFields: string[]
  /** 受管领域关系选择（仅当该分类有领域关系规格时随保存提交）。 */
  relationSelections: Record<string, string[]>
  relationHints: Array<{ field: string; text: string }>
}

const sectionForCategory = (category: string | null | undefined): FoundationTab => {
  if (category === 'character') return 'characters'
  if (category === 'relationship') return 'relationships'
  if (category === 'story_line') return 'storylines'
  if (category === 'promise_foreshadowing') return 'foreshadowing'
  if (category === 'location') return 'locations'
  if (category === 'organization_force') return 'organizations'
  if (category === 'system') return 'systems'
  if (category === 'mystery_information') return 'mystery_information'
  return 'canon_facts'
}

// ---------------- M3 基座设计（Agent 主导 + 多轮知识参考；候选 ≠ authority） ----------------

interface FdEditItem {
  key: string
  include: boolean
  kind: 'character' | 'relationship' | 'world_setting' | 'location' | 'organization' | 'system' | 'story_line' | 'promise_foreshadowing' | 'mystery_information' | 'core_conflict'
  candidate_key?: string | null
  title: string
  summary: string
  data: Record<string, string>
  listFields: string[]
  material_state: 'current' | 'future'
  source_key?: string | null
  target_key?: string | null
  source_ref?: string | null
  target_ref?: string | null
  source_title?: string
  target_title?: string
  label?: string
}

const fdKindLabel: Record<FdEditItem['kind'], string> = {
  character: '人物',
  relationship: '关系',
  world_setting: '世界',
  location: '地点',
  organization: '组织',
  system: '体系',
  story_line: '故事线',
  promise_foreshadowing: '伏笔与承诺',
  mystery_information: '悬疑信息',
  core_conflict: '核心冲突',
}

const fdFieldLabels: Record<string, string> = {
  design_summary: '摘要',
  one_line_intro: '一句话介绍',
  role_identity: '身份 / 角色',
  position_title: '职位',
  faction_org: '阵营 / 组织',
  visible_traits: '特征',
  persona_core: '人设',
  goal_desire: '目标 / 欲望',
  fear_weakness: '恐惧 / 弱点',
  inner_conflict: '内在冲突',
  background_summary: '背景',
  power_rank: '武力 / 等级',
  current_level: '当前体系等级',
  current_objective: '当前目标',
  speech_style: '说话特点',
  behavior_anchors: '行为特点',
  secrets: '秘密',
  description: '描述',
  current_state: '当前状态',
  relationship_phase: '关系阶段',
  key_history: '关键经历',
  current_tension: '当前张力',
  hidden_information: '隐瞒的信息',
  trust: '信任',
  closeness: '亲近',
  era_time_background: '时代背景',
  geographic_scope: '地理范围',
  social_structure: '社会结构',
  political_order: '政治秩序',
  economy_resources: '经济资源',
  culture_customs: '文化习俗',
  technology_level: '技术水平',
  supernatural_baseline: '超自然基线',
  important_history: '重要历史',
  hard_rules: '硬规则',
  prohibitions_taboos: '禁忌',
  known_exceptions: '例外',
  story_constraints: '故事约束',
  type: '类型',
  region_parent: '所属区域',
  physical_features: '物理特征',
  story_social_function: '叙事功能',
  controlling_organization: '控制组织',
  rules_risks: '规则 / 风险',
  purpose: '目的',
  hierarchy: '层级',
  leader_key_members: '关键成员',
  resources: '资源',
  territory_scope: '势力范围',
  rules: '规则',
  external_relationships: '外部关系',
  levels_stages: '等级 / 阶段',
  entry_progression_requirements: '进入 / 晋升要求',
  abilities_privileges: '能力 / 权限',
  limitations_costs: '限制 / 代价',
  visible_markers: '可见标记',
  exceptions: '例外',
  important_rules: '重要规则',
  goal_purpose: '目标',
  stakes: '利害',
  main_conflict: '主冲突',
  participating_characters: '参与人物',
  related_organizations_locations: '相关组织 / 地点',
  stage_progress: '阶段进展',
  dependencies: '依赖',
  expected_payoff_end_condition: '预期终局',
  setup_trigger: '埋设触发',
  reader_question_promise: '读者问题 / 承诺',
  related_entities: '相关对象',
  state: '状态',
  intended_payoff: '预期回收',
  actual_payoff: '实际回收',
  secret_fact: '秘密事实',
  who_knows: '知情者',
  who_does_not_know: '不知情者',
  mistaken_beliefs: '误解',
  reveal_status: '揭示状态',
  planned_reveal: '计划揭示',
  actual_reveal_event_chapter: '实际揭示章节',
  notes: '备注',
}

function fdDataToStrings(data: unknown, summary: string): { values: Record<string, string>; listFields: string[] } {
  const values: Record<string, string> = {}
  const listFields: string[] = []
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    Object.entries(data as Record<string, unknown>).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        values[key] = value.map((item) => String(item ?? '')).filter(Boolean).join('、')
        listFields.push(key)
      } else if (value != null) values[key] = String(value)
    })
  }
  if (summary && !values.design_summary) values.design_summary = summary
  return { values, listFields }
}

function fdStringsToData(data: Record<string, string>, listFields: string[]): Record<string, unknown> {
  const lists = new Set(listFields)
  return Object.fromEntries(Object.entries(data).filter(([, value]) => value.trim()).map(([key, value]) => [
    key,
    lists.has(key) ? value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean) : value.trim(),
  ]))
}

function fdItemsFromResult(result: FoundationDesignResult): FdEditItem[] {
  const p = result.candidate.proposal
  const items: FdEditItem[] = []
  const push = (kind: FdEditItem['kind'], list: Array<FoundationDesignItem | null>) => {
    list.forEach((entry, index) => {
      if (!entry) return
      const data = fdDataToStrings(entry.data, String(entry.summary ?? ''))
      items.push({
        key: `${kind}-${index}`, include: true, kind,
        candidate_key: entry.candidate_key,
        title: String(entry.title ?? ''), summary: String(entry.summary ?? ''),
        data: data.values,
        listFields: data.listFields,
        material_state: entry.material_state === 'current' ? 'current' : 'future',
        source_key: entry.source_key, target_key: entry.target_key,
        source_ref: entry.source_ref, target_ref: entry.target_ref,
        source_title: entry.source_title, target_title: entry.target_title, label: entry.label,
      })
    })
  }
  push('character', p.characters)
  push('relationship', p.relationships)
  push('world_setting', p.world_settings)
  push('location', p.locations ?? [])
  push('organization', p.organizations)
  push('system', p.systems ?? [])
  push('story_line', p.story_lines)
  push('promise_foreshadowing', p.promise_foreshadowing ?? [])
  push('mystery_information', p.mystery_information ?? [])
  push('core_conflict', [p.core_conflict])
  return items
}

function FoundationDesignDrawer(props: {
  projectId: string
  modelRev: number
  initialRequest?: string
  notify: (message: string) => void
  reload: () => Promise<void>
  onClose: () => void
}) {
  const { task, start, cancel, confirm } = useAuthorTask()
  const fdTask = task && task.kind === 'foundation_design' && task.projectId === props.projectId ? task : null
  const [request, setRequest] = useState(props.initialRequest ?? '')
  const [localError, setLocalError] = useState<string | null>(null)
  const [edits, setEdits] = useState<FdEditItem[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (fdTask?.status === 'candidate' && fdTask.result) {
      setEdits(fdItemsFromResult(fdTask.result as FoundationDesignResult))
    }
  }, [fdTask?.status, fdTask?.result])

  const begin = async () => {
    setLocalError(null)
    setBusy(true)
    const err = await start({
      kind: 'foundation_design', project_id: props.projectId,
      author_request: request, base_model_rev: props.modelRev,
    })
    setBusy(false)
    if (err) setLocalError(err)
  }

  const accept = async () => {
    setLocalError(null)
    setBusy(true)
    const items = edits.filter((item) => item.include).map(({ key, include, data, listFields, ...item }) => ({
      ...item,
      data: fdStringsToData(data, listFields),
    }))
    const result = await confirm('foundation_design', { items, base_model_rev: props.modelRev })
    setBusy(false)
    if (result) {
      props.notify('作品地基已更新。')
      await props.reload()
      props.onClose()
    } else if (fdTask?.error) {
      setLocalError(fdTask.error)
    }
  }

  const candidate = fdTask?.status === 'candidate' ? (fdTask.result as FoundationDesignResult | null) : null
  const working = !!fdTask && (fdTask.status === 'running' || fdTask.status === 'waiting_author' || fdTask.status === 'pending')
  return (
    <aside className="record-drawer panel foundation-design" aria-label="完善作品地基">
      <header><h2>完善作品地基</h2><button onClick={props.onClose}><X /></button></header>
      <div className="record-drawer-body">
        {!fdTask && (
          <>
            <p className="muted-note">写下你想确立的地基问题（人物、关系、世界、地点、组织、体系、故事线、伏笔与悬疑）。AI 会分解问题并参考相关写作/参考知识，给出候选；采用后才写入作品。</p>
            <textarea rows={4} value={request} onChange={(e) => setRequest(e.target.value)} placeholder="例如：为这本书设计主角结构与核心冲突…" />
            {localError && <p className="error-text">{localError}</p>}
          </>
        )}
        {working && <div className="running"><span />AI 正在分解基座问题并参考相关知识，请稍候…</div>}
        {fdTask?.status === 'failed' && <p className="error-text">{fdTask.error ?? '任务失败，请重新发起。'}</p>}
        {fdTask?.status === 'confirming' && <div className="running"><span />正在写入作品地基…</div>}
        {candidate && (
          <>
            <p><b>目标：</b>{candidate.candidate.objective}</p>
            {candidate.candidate.knowledge_notes && <p className="muted-note">知识参考：{candidate.candidate.knowledge_notes}</p>}
            {candidate.candidate.rounds.map((round, i) => (
              <p className="fd-round" key={`${round.topic}-${i}`}><b>{round.topic}</b>（参考 {round.selected_count} 条）：{round.comparison}</p>
            ))}
            {edits.map((item, index) => (
              <div className="fd-item" key={item.key}>
                <label className="fd-include">
                  <input type="checkbox" checked={item.include} onChange={(e) => setEdits(edits.map((it, i) => i === index ? { ...it, include: e.target.checked } : it))} />
                  采用
                </label>
                <span className="material-state future">{fdKindLabel[item.kind]}</span>
                <input value={item.title} onChange={(e) => setEdits(edits.map((it, i) => i === index ? { ...it, title: e.target.value } : it))} />
                {Object.entries(item.data).map(([field, value]) => (
                  <label key={field}>{fdFieldLabels[field] ?? field}<textarea rows={2} value={value} onChange={(e) => setEdits(edits.map((it, i) => i === index ? { ...it, data: { ...it.data, [field]: e.target.value } } : it))} /></label>
                ))}
              </div>
            ))}
            {candidate.candidate.assumptions.length > 0 && (
              <p className="muted-note">假设：{candidate.candidate.assumptions.join('；')}</p>
            )}
            {localError && <p className="error-text">{localError}</p>}
          </>
        )}
      </div>
      <footer>
        {!fdTask && <button className="primary" disabled={busy || !request.trim()} onClick={() => void begin()}>开始设计</button>}
        {working && <button disabled={busy} onClick={() => void cancel()}>取消</button>}
        {fdTask?.status === 'failed' && <button onClick={() => void cancel()}>关闭</button>}
        {candidate && (
          <>
            <button disabled={busy} onClick={() => void cancel()}>丢弃</button>
            <button className="primary" disabled={busy || !edits.some((it) => it.include)} onClick={() => void accept()}>采用所选条目</button>
          </>
        )}
      </footer>
    </aside>
  )
}

export function FoundationPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [designOpen, setDesignOpen] = useState(false)
  const [designPrefill, setDesignPrefill] = useState<string | undefined>(undefined)
  const [tab, setTab] = useState<FoundationTab>('characters')
  const [activeGroupLabel, setActiveGroupLabel] = useState(groupForTab('characters').label)
  const [recordForm, setRecordForm] = useState<RecordForm | null>(null)
  const [sharedEditor, setSharedEditor] = useState<{ kind: 'character' | 'relationship'; entry: ProjectDataEntry | null } | null>(null)
  const [detailEntry, setDetailEntry] = useState<ProjectDataEntry | null>(null)
  const [genreTags, setGenreTags] = useState('')
  const [narrativeMode, setNarrativeMode] = useState('')
  const handoffRef = useRef<string | null>(null)

  const tabMeta = tabs.find((item) => item.key === tab) ?? tabs[0]
  const activeGroup = tabGroups.find((group) => group.label === activeGroupLabel) ?? groupForTab(tab)
  const entries = useMemo(() => controller.data?.sections[tab] ?? [], [controller.data, tab])
  const fields = fieldsForTab(tab)
  const characters = controller.data?.sections.characters ?? []
  const readonlyDetailFields = useMemo(() => detailEntry ? describeRecord(detailEntry) : [], [detailEntry])

  useEffect(() => {
    setRecordForm(null)
    setSharedEditor(null)
    setDetailEntry(null)
    handoffRef.current = null
    setActiveGroupLabel(groupForTab('characters').label)
  }, [selected?.project_id])

  useEffect(() => {
    setActiveGroupLabel(groupForTab(tab).label)
  }, [tab])

  useEffect(() => {
    const profile = controller.data?.story_bible_profile
    if (!profile) return
    setGenreTags(profile.genre_tags.join('、'))
    setNarrativeMode(profile.narrative_mode ?? '')
  }, [controller.data?.story_bible_profile])

  const beginCreate = () => {
    if (tab === 'characters' || tab === 'relationships') {
      setSharedEditor({ kind: tab === 'characters' ? 'character' : 'relationship', entry: null })
      return
    }
    const relationInit = initializeRelationSelections({
      category: tabMeta.category, sourceRef: null, record: {}, data: controller.data,
    })
    setRecordForm({
      mode: 'create', ref: null, title: '', material_state: tab === 'storylines' ? 'future' : 'current',
      category: tabMeta.category,
      data: Object.fromEntries(fields.map(([key]) => [key, ''])), extraFields: [], preservedData: {}, knownListFields: [],
      relationSelections: relationInit.selections, relationHints: relationInit.hints,
    })
  }

  const beginEdit = (entry: ProjectDataEntry) => {
    if (!entry.editable || !entry.source_ref) return
    if (tab === 'characters' || tab === 'relationships') {
      setSharedEditor({ kind: tab === 'characters' ? 'character' : 'relationship', entry })
      return
    }
    const flexible = splitEditorData(entry, fields)
    const relationInit = initializeRelationSelections({
      category: entry.category || tabMeta.category, sourceRef: entry.source_ref,
      record: recordObject(entry), data: controller.data,
    })
    setRecordForm({
      mode: 'edit', ref: entry.source_ref, title: entry.label,
      material_state: entry.status === 'future' ? 'future' : 'current',
      category: entry.category || tabMeta.category,
      data: flexible.values, extraFields: flexible.custom,
      preservedData: flexible.preserved, knownListFields: [...flexible.knownListFields],
      relationSelections: relationInit.selections, relationHints: relationInit.hints,
    })
  }

  useEffect(() => {
    if (!selected || controller.loading || !controller.data) return
    const handoff = actions.consumeFoundationEditHandoff()
    if (!handoff || handoff.project_id !== selected.project_id || handoffRef.current === handoff.source_ref) return
    const sections: FoundationTab[] = [
      'characters', 'relationships', 'canon_facts', 'locations', 'organizations', 'systems',
      'storylines', 'foreshadowing', 'mystery_information',
    ]
    for (const section of sections) {
      const entry = controller.data.sections[section].find((item) => item.source_ref === handoff.source_ref)
      if (entry) {
        handoffRef.current = handoff.source_ref
        setTab(sectionForCategory(entry.category))
        if (entry.category === 'relationship' || section === 'relationships') {
          setSharedEditor({ kind: 'relationship', entry })
        } else if (section === 'characters') {
          setSharedEditor({ kind: 'character', entry })
        } else {
          const entryFields = fieldsForTab(section)
          const flexible = splitEditorData(entry, entryFields)
          const relationInit = initializeRelationSelections({
            category: entry.category || 'world_setting', sourceRef: entry.source_ref,
            record: recordObject(entry), data: controller.data,
          })
          setRecordForm({
            mode: 'edit', ref: entry.source_ref ?? null, title: entry.label,
            material_state: entry.status === 'future' ? 'future' : 'current',
            category: entry.category || 'world_setting', data: flexible.values,
            extraFields: flexible.custom, preservedData: flexible.preserved,
            knownListFields: [...flexible.knownListFields],
            relationSelections: relationInit.selections, relationHints: relationInit.hints,
          })
        }
        return
      }
    }
  }, [actions, characters, controller.data, controller.loading, selected])

  useEffect(() => {
    if (!selected) return
    const handoff = actions.consumeFoundationDesignHandoff()
    if (!handoff || handoff.project_id !== selected.project_id) return
    setDesignPrefill(handoff.prefill)
    setDesignOpen(true)
  }, [actions, selected])

  if (!selected) return <div className="empty-state">请先选择正式作品。</div>

  const saveRecord = async () => {
    if (!recordForm || !recordForm.title.trim()) return
    let data: Record<string, unknown> = {
      ...recordForm.preservedData,
    }
    Object.entries(recordForm.data).forEach(([key, value]) => {
      if (!value.trim()) return
      data[key] = recordForm.knownListFields.includes(key)
        ? value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
        : value.trim()
    })
    for (const field of recordForm.extraFields) {
      const key = field.key.trim()
      if (!key || !field.value.trim()) continue
      data[key] = field.isList ? field.value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean) : field.value.trim()
    }
    const specs = RELATION_SPECS_BY_SOURCE_CATEGORY[recordForm.category] ?? []
    const manageRelations = specs.length > 0
    // 作者已保存规范化选择后，停止写回重复的遗留关系文本字段。
    data = stripLegacyRelationFields(data, legacyFieldsToStrip(recordForm.category, recordForm.relationSelections))
    const relations = manageRelations ? relationSelections(recordForm.relationSelections) : undefined
    const ok = recordForm.mode === 'create'
      ? await controller.createFoundation({
          category: recordForm.category, title: recordForm.title.trim(),
          material_state: recordForm.material_state, data, relations,
        })
      : await controller.updateFoundation({
          ref: recordForm.ref as string, title: recordForm.title.trim(),
          material_state: recordForm.material_state, data, relations,
        })
    if (ok) setRecordForm(null)
  }

  const retire = async (entry: ProjectDataEntry) => {
    if (!entry.editable || !entry.source_ref) return
    if (!window.confirm(`确认退役“${entry.label || '这条记录'}”？记录会保留历史，不会直接删除。`)) return
    const ok = await controller.retireFoundation(entry.source_ref)
    if (ok) {
      setRecordForm(null)
    }
  }

  const saveProfile = async () => {
    const profile = controller.data?.story_bible_profile
    if (!profile) return
    await controller.saveProfile({
      genre_tags: genreTags.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean),
      narrative_mode: narrativeMode.trim() || null,
      active_modules: profile.active_modules,
      field_config: profile.field_config,
    })
  }

  return (
    <div className="foundation-page">
      <div className="foundation-direction">
        <section className="panel"><h3>作品方向</h3><p>{controller.data?.work_direction || '当前尚未记录。'}</p></section>
        <section className="panel"><h3>读者期待</h3><p>{controller.data?.reader_promise || '当前尚未记录。'}</p></section>
      </div>

      <section className="panel foundation-profile">
        <h3>作品基础信息</h3>
        <label>题材标签<input value={genreTags} onChange={(event) => setGenreTags(event.target.value)} placeholder="例如：历史、悬疑" /></label>
        <label>叙事方式<input value={narrativeMode} onChange={(event) => setNarrativeMode(event.target.value)} placeholder="明确时填写，例如：第三人称限知" /></label>
        <button onClick={() => void saveProfile()} disabled={controller.saving}><Save /> 保存基础信息</button>
      </section>

      <section className="panel foundation-main">
        <header className="foundation-toolbar">
          <div className="foundation-nav">
            <div className="foundation-group-tabs" aria-label="作品地基分组">
            {tabGroups.map((group) => (
              <button key={group.label} className={activeGroup.label === group.label ? 'active' : ''} onClick={() => { setActiveGroupLabel(group.label); setTab(group.tabs[0]); setRecordForm(null); setSharedEditor(null); setDetailEntry(null) }}>{group.label}</button>
            ))}
            </div>
            <div className="foundation-tabs" aria-label={`${activeGroup.label}分类`}>
              {activeGroup.tabs.map((key) => {
                const item = tabs.find((candidate) => candidate.key === key) as typeof tabs[number]
                const { label, Icon } = item
                return <button key={key} className={tab === key ? 'active' : ''} onClick={() => { setTab(key); setRecordForm(null); setSharedEditor(null); setDetailEntry(null) }}><Icon /> {label}</button>
              })}
            </div>
          </div>
          <div className="foundation-toolbar-actions"><button onClick={() => { setDesignPrefill(undefined); setDesignOpen(true) }}><Sparkles /> 完善作品地基</button><button className="primary" onClick={beginCreate}><Plus /> 新增</button></div>
        </header>

        {controller.loading && <div className="empty-state">正在加载作品地基…</div>}
        {controller.error && <p className="error-text">{controller.error}</p>}
        {!controller.loading && entries.length === 0 && <div className="empty-state">当前尚未记录{tabMeta.label}，可以直接新增。</div>}

        {(() => {
          const retiredFoundation = controller.data?.retired.foundation ?? []
          const retiredRelationships = controller.data?.retired.relationships ?? []
          if (retiredFoundation.length === 0 && retiredRelationships.length === 0) return null
          return (
            <details className="foundation-retired">
              <summary>已退役（{retiredFoundation.length + retiredRelationships.length}）</summary>
              <ul>
                {retiredFoundation.map((entry) => (
                  <li key={`retired-f-${entry.source_ref ?? entry.label}`}>
                    <span className="foundation-retired-name">{entry.label || '（未命名记录）'}</span>
                    <span className="muted-note">{entry.category === 'character' ? '人物' : '地基记录'}</span>
                    {entry.source_ref && (
                      <button disabled={controller.saving} onClick={() => void controller.restoreFoundation(entry.source_ref as string)}>恢复</button>
                    )}
                  </li>
                ))}
                {retiredRelationships.map((entry) => (
                  <li key={`retired-r-${entry.source_ref ?? entry.label}`}>
                    <span className="foundation-retired-name">{entry.label || '（未命名关系）'}</span>
                    <span className="muted-note">关系</span>
                    {entry.source_ref && (
                      <button disabled={controller.saving} onClick={() => void controller.restoreRelationship(entry.source_ref as string)}>恢复</button>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )
        })()}

        <div className="foundation-cards">
          {entries.map((entry) => {
            const character = tab === 'characters' ? compactCharacter(entry) : null
            const details = character
              ? [
                  ...(character.intro ? [{ key: 'one_line_intro', label: '一句话介绍', value: character.intro }] : []),
                  ...(character.role ? [{ key: 'role_identity', label: '身份 / 职位', value: character.role }] : []),
                ]
              : describeRecord(entry).slice(0, 2)
            return (
              <article className="foundation-card" key={`${tab}-${entry.id ?? entry.label}`}>
                <div className="foundation-card-head">
                  {character && <span className="character-avatar" style={{ '--avatar-hue': character.avatar.hue } as CSSProperties} aria-hidden="true">{character.avatar.text}</span>}
                  <h3>{entry.label || '（未命名条目）'}</h3>
                  <span className={`material-state ${entry.status === 'future' ? 'future' : 'current'}`}>
                    {entry.status === 'future' ? '规划中' : '当前'}
                  </span>
                </div>
                {details.length === 0 && <p className="muted-note">暂无更多已记录信息。</p>}
                {details.map((detail) => <p key={detail.key}><b>{detail.label}：</b>{detail.value}</p>)}
                <footer>
                  {entry.editable
                    ? <button onClick={() => beginEdit(entry)}><Pencil /> 查看 / 编辑</button>
                    : <button onClick={() => setDetailEntry(entry)}>查看详情</button>}
                </footer>
              </article>
            )
          })}
        </div>
      </section>

      {recordForm && (
        <aside className="record-drawer panel" aria-label={`${recordForm.mode === 'create' ? '新增' : '编辑'}${tabMeta.label}`}>
          <header><h2>{recordForm.mode === 'create' ? '新增' : '编辑'}{tabMeta.label}</h2><button onClick={() => setRecordForm(null)}><X /></button></header>
          <div className="record-drawer-body">
          <label>名称<input value={recordForm.title} onChange={(event) => setRecordForm({ ...recordForm, title: event.target.value })} /></label>
          <label>状态<select value={recordForm.material_state} onChange={(event) => setRecordForm({ ...recordForm, material_state: event.target.value as MaterialState })}><option value="current">当前</option><option value="future">规划中</option></select></label>
          {(RELATION_SPECS_BY_SOURCE_CATEGORY[recordForm.category] ?? []).map((spec: RelationSpec) => (
            <RelationSelector
              key={spec.relation_kind}
              label={spec.label}
              options={relationOptions(controller.data, spec.targetCategories)}
              selected={recordForm.relationSelections[spec.relation_kind] ?? []}
              onChange={(next) => setRecordForm({
                ...recordForm,
                relationSelections: { ...recordForm.relationSelections, [spec.relation_kind]: next },
              })}
              excludeSelf={recordForm.ref}
            />
          ))}
          {recordForm.relationHints.map((hint) => <p className="muted-note legacy-relation-hint" key={hint.field}>{hint.text}</p>)}
          <div className="record-fields">
            {fields.map(([key, label]) => (
              <label key={key}>{label}<textarea rows={key === 'background_summary' || key === 'notes' ? 3 : 2} value={recordForm.data[key] ?? ''} onChange={(event) => setRecordForm({ ...recordForm, data: { ...recordForm.data, [key]: event.target.value } })} /></label>
            ))}
            {recordForm.extraFields.map((field, index) => (
              <div className="custom-field-row" key={`${field.key}-${index}`}>
                <input aria-label="自定义字段名" value={field.key} onChange={(event) => setRecordForm({ ...recordForm, extraFields: recordForm.extraFields.map((item, i) => i === index ? { ...item, key: event.target.value } : item) })} placeholder="自定义字段名" />
                <textarea aria-label="自定义字段值" rows={2} value={field.value} onChange={(event) => setRecordForm({ ...recordForm, extraFields: recordForm.extraFields.map((item, i) => i === index ? { ...item, value: event.target.value } : item) })} placeholder="内容" />
                <button aria-label="删除自定义字段" onClick={() => setRecordForm({ ...recordForm, extraFields: recordForm.extraFields.filter((_, i) => i !== index) })}><Trash2 /></button>
              </div>
            ))}
            <button onClick={() => setRecordForm({ ...recordForm, extraFields: [...recordForm.extraFields, { key: '', value: '', isList: false }] })}><Plus /> 添加自定义字段</button>
          </div>
          </div>
          <footer>
            {recordForm.mode === 'edit' && <button className="danger" onClick={() => void retire({ source_ref: recordForm.ref, editable: true } as ProjectDataEntry)}><Trash2 /> 退役</button>}
            <button className="primary" disabled={controller.saving || !recordForm.title.trim()} onClick={() => void saveRecord()}><Save /> {controller.saving ? '保存中…' : '保存'}</button>
          </footer>
        </aside>
      )}

      {sharedEditor?.kind === 'character' && <CharacterEditor key={sharedEditor.entry?.source_ref ?? 'new-character'} entry={sharedEditor.entry} controller={controller} onClose={() => setSharedEditor(null)} />}
      {sharedEditor?.kind === 'relationship' && <RelationshipEditor key={sharedEditor.entry?.source_ref ?? 'new-relationship'} entry={sharedEditor.entry} characters={characters} controller={controller} onClose={() => setSharedEditor(null)} />}
      {detailEntry && (
        <aside className="record-drawer panel" aria-label={`${detailEntry.label}详情`}>
          <header><h2>{detailEntry.label || '未命名记录'}</h2><button onClick={() => setDetailEntry(null)}><X /></button></header>
          <div className="record-drawer-body">
          <p><span className={`material-state ${detailEntry.status === 'future' ? 'future' : 'current'}`}>{authorStatusLabel(detailEntry.status)}</span></p>
          <p className="muted-note">{authorSourceLabel(detailEntry.source_kind)}</p>
          <div className="record-fields">
            {readonlyDetailFields.length === 0 && <p className="muted-note">暂无更多已记录信息。</p>}
            {readonlyDetailFields.map((field) => <p key={field.key}><b>{field.label}：</b>{field.value}</p>)}
          </div>
          </div>
        </aside>
      )}

      {designOpen && selected && (
        <FoundationDesignDrawer
          projectId={selected.project_id}
          modelRev={controller.data?.model_rev ?? 0}
          initialRequest={designPrefill}
          notify={actions.notify}
          reload={controller.reload}
          onClose={() => setDesignOpen(false)}
        />
      )}
    </div>
  )
}
