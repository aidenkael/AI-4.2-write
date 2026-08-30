import { Check, FileCheck2, GitBranch, MapPin, Pencil, Plus, Save, Trash2, UserRound, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ProjectDataEntry } from '../bridge/client'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { describeRecord } from '../features/storyMap/storyMapModel'

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

const characterFields = [
  ['aliases', '别名'], ['one_line_intro', '一句话介绍'], ['role_identity', '角色 / 身份'],
  ['position_title', '职位'], ['faction_org', '阵营 / 组织'], ['visible_traits', '可见特征'],
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
    ['participating_characters', '参与人物'], ['related_organizations_locations', '相关组织 / 地点'],
    ['stage_progress', '阶段 / 进度'], ['dependencies', '依赖'],
    ['expected_payoff_end_condition', '预期回收 / 结束条件'], ['notes', '备注'],
  ],
  foreshadowing: [
    ['setup_trigger', '埋设 / 触发'], ['reader_question_promise', '读者问题 / 承诺'],
    ['related_entities', '相关对象'], ['state', '状态'], ['intended_payoff', '计划回收'],
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
}

interface RelationshipForm {
  mode: 'create' | 'edit'
  ref: string | null
  label: string
  source_ref: string
  target_ref: string
  material_state: MaterialState
  description: string
  state: string
  notes: string
  relationship_phase: string
  key_history: string
  current_tension: string
  hidden_information: string
  trust: string
  closeness: string
  preservedData: Record<string, unknown>
}

function recordObject(entry: ProjectDataEntry): Record<string, unknown> {
  return entry.record && typeof entry.record === 'object' && !Array.isArray(entry.record)
    ? entry.record as Record<string, unknown>
    : {}
}

function stringData(entry: ProjectDataEntry, fields: readonly (readonly [string, string])[]) {
  const record = recordObject(entry)
  return Object.fromEntries(fields.map(([key]) => [key, typeof record[key] === 'string' ? record[key] as string : '']))
}

const injectedKeys = new Set([
  'id', 'name', 'authority', 'source', 'target', 'source_name', 'target_name', 'relationship',
  'source_ref', 'source_kind', 'material_state',
])

function flexibleData(entry: ProjectDataEntry, fields: readonly (readonly [string, string])[]) {
  const record = recordObject(entry)
  const known = new Set(fields.map(([key]) => key))
  const extraFields: Array<{ key: string; value: string; isList: boolean }> = []
  const preservedData: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(record)) {
    if (known.has(key) || injectedKeys.has(key)) continue
    if (['planning_source_ref', 'source_state_ref', 'supersedes_state_ref', 'settlement_provenance'].includes(key)) {
      preservedData[key] = value
    } else if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      extraFields.push({ key, value: String(value), isList: false })
    } else if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
      extraFields.push({ key, value: value.join('、'), isList: true })
    } else {
      preservedData[key] = value
    }
  }
  return { extraFields, preservedData }
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

const optionalModules = [
  ['power_progression', '成长 / 战力'], ['career_rank', '职业 / 职级'],
  ['economy_resources', '经济 / 资源'], ['politics_factions', '政治 / 阵营'],
  ['technology', '科技'], ['supernatural_rules', '超自然规则'],
  ['romance_social', '情感 / 社交'], ['mystery_information', '悬疑信息'], ['custom', '自定义'],
] as const

const characterInitial = (entry: ProjectDataEntry) => {
  const label = entry.label.trim()
  return label ? label.slice(0, 1).toUpperCase() : '？'
}

function relationshipEndpointRefs(record: Record<string, unknown>, characters: ProjectDataEntry[]): [string, string] {
  const raw = Array.isArray(record.targets) ? record.targets
    : Array.isArray(record.characters) ? record.characters
      : Array.isArray(record.between) ? record.between
        : Array.isArray(record.participants) ? record.participants
          : [record.source ?? record.from, record.target ?? record.to]
  const resolve = (value: unknown) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const item = value as Record<string, unknown>
      value = item.id ?? item.name ?? item.label
    }
    if (typeof value !== 'string' || !value.trim()) return ''
    const needle = value.trim()
    const matches = characters.filter((character) => {
      const data = recordObject(character)
      return [character.id, character.source_ref, character.label, data.id, data.name, data.label].some((candidate) => candidate === needle)
    })
    return matches.length === 1 ? matches[0].source_ref ?? '' : ''
  }
  return [resolve(raw[0]), resolve(raw[1])]
}

export function FoundationPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [tab, setTab] = useState<FoundationTab>('characters')
  const [recordForm, setRecordForm] = useState<RecordForm | null>(null)
  const [relationshipForm, setRelationshipForm] = useState<RelationshipForm | null>(null)
  const [genreTags, setGenreTags] = useState('')
  const [narrativeMode, setNarrativeMode] = useState('')
  const [activeModules, setActiveModules] = useState<string[]>([])
  const [characterOptionalFields, setCharacterOptionalFields] = useState('')
  const handoffRef = useRef<string | null>(null)

  const tabMeta = tabs.find((item) => item.key === tab) ?? tabs[0]
  const entries = useMemo(() => controller.data?.sections[tab] ?? [], [controller.data, tab])
  const fields = fieldsForTab(tab)
  const characters = controller.data?.sections.characters ?? []

  useEffect(() => {
    const profile = controller.data?.story_bible_profile
    if (!profile) return
    setGenreTags(profile.genre_tags.join('、'))
    setNarrativeMode(profile.narrative_mode ?? '')
    setActiveModules(profile.active_modules)
    const characterConfig = profile.field_config.character
    const optionalFields = characterConfig && typeof characterConfig === 'object' && !Array.isArray(characterConfig)
      ? (characterConfig as Record<string, unknown>).optional_fields
      : []
    setCharacterOptionalFields(Array.isArray(optionalFields)
      ? optionalFields.filter((item): item is string => typeof item === 'string').join('、')
      : '')
  }, [controller.data?.story_bible_profile])

  const beginCreate = () => {
    if (tab === 'relationships') {
      setRelationshipForm({
        mode: 'create', ref: null, label: '', source_ref: '', target_ref: '',
        material_state: 'current', description: '', state: '', notes: '',
        relationship_phase: '', key_history: '', current_tension: '', hidden_information: '',
        trust: '', closeness: '', preservedData: {},
      })
      return
    }
    setRecordForm({
      mode: 'create', ref: null, title: '', material_state: tab === 'storylines' ? 'future' : 'current',
      category: tabMeta.category,
      data: Object.fromEntries(fields.map(([key]) => [key, ''])), extraFields: [], preservedData: {},
    })
  }

  const beginEdit = (entry: ProjectDataEntry) => {
    if (!entry.editable || !entry.source_ref) return
    if (tab === 'relationships') {
      const record = recordObject(entry)
      const [sourceRef, targetRef] = relationshipEndpointRefs(record, characters)
      setRelationshipForm({
        mode: 'edit', ref: entry.source_ref, label: entry.label,
        source_ref: sourceRef, target_ref: targetRef,
        material_state: entry.status === 'future' ? 'future' : 'current',
        description: String(record.description ?? ''), state: String(record.current_state ?? record.state ?? record.status ?? ''),
        notes: String(record.notes ?? ''),
        relationship_phase: String(record.relationship_phase ?? ''),
        key_history: String(record.key_history ?? ''), current_tension: String(record.current_tension ?? ''),
        hidden_information: String(record.hidden_information ?? ''),
        trust: String(record.trust ?? ''), closeness: String(record.closeness ?? ''),
        preservedData: Object.fromEntries(
          Object.entries(record).filter(([key]) => ['planning_source_ref', 'source_state_ref', 'supersedes_state_ref', 'settlement_provenance'].includes(key)),
        ),
      })
      return
    }
    const flexible = flexibleData(entry, fields)
    setRecordForm({
      mode: 'edit', ref: entry.source_ref, title: entry.label,
      material_state: entry.status === 'future' ? 'future' : 'current',
      category: entry.category || tabMeta.category,
      data: stringData(entry, fields),
      ...flexible,
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
        const record = recordObject(entry)
        if (entry.category === 'relationship' || section === 'relationships') {
          const [sourceRef, targetRef] = relationshipEndpointRefs(record, characters)
          setRelationshipForm({
            mode: 'edit', ref: entry.source_ref ?? null, label: entry.label,
            source_ref: sourceRef, target_ref: targetRef,
            material_state: entry.status === 'future' ? 'future' : 'current',
            description: String(record.description ?? ''), state: String(record.current_state ?? record.state ?? record.status ?? ''),
            notes: String(record.notes ?? ''), relationship_phase: String(record.relationship_phase ?? ''),
            key_history: String(record.key_history ?? ''), current_tension: String(record.current_tension ?? ''),
            hidden_information: String(record.hidden_information ?? ''), trust: String(record.trust ?? ''),
            closeness: String(record.closeness ?? ''), preservedData: {},
          })
        } else {
          const entryFields = fieldsForTab(section)
          setRecordForm({
            mode: 'edit', ref: entry.source_ref ?? null, title: entry.label,
            material_state: entry.status === 'future' ? 'future' : 'current',
            category: entry.category || 'world_setting', data: stringData(entry, entryFields),
            ...flexibleData(entry, entryFields),
          })
        }
        return
      }
    }
  }, [actions, characters, controller.data, controller.loading, selected])

  if (!selected) return <div className="empty-state">请先选择正式作品。</div>

  const saveRecord = async () => {
    if (!recordForm || !recordForm.title.trim()) return
    const data: Record<string, unknown> = {
      ...recordForm.preservedData,
      ...Object.fromEntries(Object.entries(recordForm.data).filter(([, value]) => value.trim())),
    }
    for (const field of recordForm.extraFields) {
      const key = field.key.trim()
      if (!key || !field.value.trim()) continue
      data[key] = field.isList ? field.value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean) : field.value.trim()
    }
    const ok = recordForm.mode === 'create'
      ? await controller.createFoundation({
          category: recordForm.category, title: recordForm.title.trim(),
          material_state: recordForm.material_state, data,
        })
      : await controller.updateFoundation({
          ref: recordForm.ref as string, title: recordForm.title.trim(),
          material_state: recordForm.material_state, data,
        })
    if (ok) setRecordForm(null)
  }

  const saveRelationship = async () => {
    if (!relationshipForm || !relationshipForm.label.trim() || !relationshipForm.source_ref || !relationshipForm.target_ref) return
    const data = {
      ...relationshipForm.preservedData,
      ...(relationshipForm.description.trim() ? { description: relationshipForm.description.trim() } : {}),
      ...(relationshipForm.state.trim() ? { current_state: relationshipForm.state.trim() } : {}),
      ...(relationshipForm.relationship_phase.trim() ? { relationship_phase: relationshipForm.relationship_phase.trim() } : {}),
      ...(relationshipForm.key_history.trim() ? { key_history: relationshipForm.key_history.trim() } : {}),
      ...(relationshipForm.current_tension.trim() ? { current_tension: relationshipForm.current_tension.trim() } : {}),
      ...(relationshipForm.hidden_information.trim() ? { hidden_information: relationshipForm.hidden_information.trim() } : {}),
      ...(relationshipForm.trust.trim() ? { trust: relationshipForm.trust.trim() } : {}),
      ...(relationshipForm.closeness.trim() ? { closeness: relationshipForm.closeness.trim() } : {}),
      ...(relationshipForm.notes.trim() ? { notes: relationshipForm.notes.trim() } : {}),
    }
    const payload = {
      source_ref: relationshipForm.source_ref, target_ref: relationshipForm.target_ref,
      label: relationshipForm.label.trim(), material_state: relationshipForm.material_state, data,
    }
    const ok = relationshipForm.mode === 'create'
      ? await controller.createRelationship(payload)
      : await controller.updateRelationship({ ref: relationshipForm.ref as string, ...payload })
    if (ok) setRelationshipForm(null)
  }

  const retire = async (entry: ProjectDataEntry) => {
    if (!entry.editable || !entry.source_ref) return
    const ok = tab === 'relationships'
      ? await controller.retireRelationship(entry.source_ref)
      : await controller.retireFoundation(entry.source_ref)
    if (ok) {
      setRecordForm(null)
      setRelationshipForm(null)
    }
  }

  const saveProfile = async () => {
    const currentConfig = controller.data?.story_bible_profile.field_config ?? {}
    const currentCharacterConfig = currentConfig.character
    const optionalFields = characterOptionalFields
      .split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
    await controller.saveProfile({
      genre_tags: genreTags.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean),
      narrative_mode: narrativeMode.trim() || null,
      active_modules: activeModules,
      field_config: {
        ...currentConfig,
        character: {
          ...(currentCharacterConfig && typeof currentCharacterConfig === 'object' && !Array.isArray(currentCharacterConfig)
            ? currentCharacterConfig as Record<string, unknown>
            : {}),
          optional_fields: optionalFields,
        },
      },
    })
  }

  return (
    <div className="foundation-page">
      <div className="foundation-direction">
        <section className="panel"><h3>作品方向</h3><p>{controller.data?.work_direction || '当前尚未记录。'}</p></section>
        <section className="panel"><h3>读者期待</h3><p>{controller.data?.reader_promise || '当前尚未记录。'}</p></section>
      </div>

      <section className="panel foundation-profile">
        <h3>本书资料结构</h3>
        <p className="muted-note">控制本书需要显示的可选领域；隐藏模块不会删除已经记录的内容。</p>
        <label>题材标签<input value={genreTags} onChange={(event) => setGenreTags(event.target.value)} placeholder="例如：历史、悬疑" /></label>
        <label>叙事方式<input value={narrativeMode} onChange={(event) => setNarrativeMode(event.target.value)} placeholder="明确时填写，例如：第三人称限知" /></label>
        <label>人物可选字段<input value={characterOptionalFields} onChange={(event) => setCharacterOptionalFields(event.target.value)} placeholder="按本书需要填写，例如：年龄状态、当前地点、声誉" /></label>
        <div className="profile-modules">
          {optionalModules.map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={activeModules.includes(key)}
                onChange={(event) => setActiveModules((items) => event.target.checked
                  ? [...items.filter((item) => item !== key), key]
                  : items.filter((item) => item !== key))}
              />
              {label}
            </label>
          ))}
        </div>
        <button onClick={() => void saveProfile()} disabled={controller.saving}><Save /> 保存本书结构</button>
      </section>

      <section className="panel foundation-main">
        <header className="foundation-toolbar">
          <div className="foundation-tabs">
            {tabs.map(({ key, label, Icon }) => (
              <button key={key} className={tab === key ? 'active' : ''} onClick={() => { setTab(key); setRecordForm(null); setRelationshipForm(null) }}>
                <Icon /> {label}
              </button>
            ))}
          </div>
          <button className="primary" onClick={beginCreate}><Plus /> 新增{tabMeta.label}</button>
        </header>

        {controller.data?.settlement.status !== 'synchronized' && (
          <div className="sync-warning">有 {controller.data?.settlement.pending_count ?? 0} 项变更等待同步；显式编辑已保存，派生状态可能暂未完整刷新。</div>
        )}
        {controller.loading && <div className="empty-state">正在加载作品地基…</div>}
        {controller.error && <p className="error-text">{controller.error}</p>}
        {!controller.loading && entries.length === 0 && <div className="empty-state">当前尚未记录{tabMeta.label}，可以直接新增。</div>}

        <div className="foundation-cards">
          {entries.map((entry) => {
            const details = describeRecord(entry)
            return (
              <article className="foundation-card" key={`${tab}-${entry.id ?? entry.label}`}>
                <div className="foundation-card-head">
                  {tab === 'characters' && <span className="character-avatar" aria-hidden="true">{characterInitial(entry)}</span>}
                  <h3>{entry.label || '（未命名条目）'}</h3>
                  <span className={`material-state ${entry.status === 'future' ? 'future' : 'current'}`}>
                    {entry.status === 'future' ? '规划中' : '当前'}
                  </span>
                </div>
                {details.length === 0 && <p className="muted-note">暂无更多已记录信息。</p>}
                {details.map((detail) => <p key={detail.key}><b>{detail.label}：</b>{detail.value}</p>)}
                <footer>
                  {entry.editable && <button onClick={() => beginEdit(entry)}><Pencil /> 编辑</button>}
                  {!entry.editable && <span className="muted-note">来自已采用正文与作品状态</span>}
                </footer>
              </article>
            )
          })}
        </div>
      </section>

      {recordForm && (
        <aside className="record-drawer panel" aria-label={`${recordForm.mode === 'create' ? '新增' : '编辑'}${tabMeta.label}`}>
          <header><h2>{recordForm.mode === 'create' ? '新增' : '编辑'}{tabMeta.label}</h2><button onClick={() => setRecordForm(null)}><X /></button></header>
          <label>名称<input value={recordForm.title} onChange={(event) => setRecordForm({ ...recordForm, title: event.target.value })} /></label>
          <label>状态<select value={recordForm.material_state} onChange={(event) => setRecordForm({ ...recordForm, material_state: event.target.value as MaterialState })}><option value="current">当前有效</option><option value="future">未来规划</option></select></label>
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
          <footer>
            {recordForm.mode === 'edit' && <button className="danger" onClick={() => void retire({ source_ref: recordForm.ref, editable: true } as ProjectDataEntry)}><Trash2 /> 退役</button>}
            <button className="primary" disabled={controller.saving || !recordForm.title.trim()} onClick={() => void saveRecord()}><Save /> {controller.saving ? '保存中…' : '保存'}</button>
          </footer>
        </aside>
      )}

      {relationshipForm && (
        <aside className="record-drawer panel" aria-label={`${relationshipForm.mode === 'create' ? '新增' : '编辑'}关系`}>
          <header><h2>{relationshipForm.mode === 'create' ? '新增' : '编辑'}关系</h2><button onClick={() => setRelationshipForm(null)}><X /></button></header>
          <label>关系名称<input value={relationshipForm.label} onChange={(event) => setRelationshipForm({ ...relationshipForm, label: event.target.value })} /></label>
          <div className="relationship-endpoints">
            <label>人物 A<select value={relationshipForm.source_ref} onChange={(event) => setRelationshipForm({ ...relationshipForm, source_ref: event.target.value })}><option value="">请选择</option>{characters.map((entry) => <option key={entry.source_ref ?? entry.id ?? entry.label} value={entry.source_ref ?? ''}>{entry.label} · {entry.status === 'future' ? '规划中' : '当前'}</option>)}</select></label>
            <label>人物 B<select value={relationshipForm.target_ref} onChange={(event) => setRelationshipForm({ ...relationshipForm, target_ref: event.target.value })}><option value="">请选择</option>{characters.map((entry) => <option key={entry.source_ref ?? entry.id ?? entry.label} value={entry.source_ref ?? ''}>{entry.label} · {entry.status === 'future' ? '规划中' : '当前'}</option>)}</select></label>
          </div>
          <label>状态<select value={relationshipForm.material_state} onChange={(event) => setRelationshipForm({ ...relationshipForm, material_state: event.target.value as MaterialState })}><option value="current">当前有效</option><option value="future">未来规划</option></select></label>
          <label>描述<textarea rows={3} value={relationshipForm.description} onChange={(event) => setRelationshipForm({ ...relationshipForm, description: event.target.value })} /></label>
          <label>关系状态<input value={relationshipForm.state} onChange={(event) => setRelationshipForm({ ...relationshipForm, state: event.target.value })} placeholder="例如：紧张、合作、疏远" /></label>
          <label>关系阶段<input value={relationshipForm.relationship_phase} onChange={(event) => setRelationshipForm({ ...relationshipForm, relationship_phase: event.target.value })} /></label>
          <label>关键经历<textarea rows={3} value={relationshipForm.key_history} onChange={(event) => setRelationshipForm({ ...relationshipForm, key_history: event.target.value })} /></label>
          <label>当前张力<textarea rows={2} value={relationshipForm.current_tension} onChange={(event) => setRelationshipForm({ ...relationshipForm, current_tension: event.target.value })} /></label>
          <label>隐瞒的信息<textarea rows={2} value={relationshipForm.hidden_information} onChange={(event) => setRelationshipForm({ ...relationshipForm, hidden_information: event.target.value })} /></label>
          <label>信任（可选）<input value={relationshipForm.trust} onChange={(event) => setRelationshipForm({ ...relationshipForm, trust: event.target.value })} /></label>
          <label>亲近（可选）<input value={relationshipForm.closeness} onChange={(event) => setRelationshipForm({ ...relationshipForm, closeness: event.target.value })} /></label>
          <label>备注<textarea rows={3} value={relationshipForm.notes} onChange={(event) => setRelationshipForm({ ...relationshipForm, notes: event.target.value })} /></label>
          <footer>
            {relationshipForm.mode === 'edit' && <button className="danger" onClick={() => void retire({ source_ref: relationshipForm.ref, editable: true } as ProjectDataEntry)}><Trash2 /> 退役</button>}
            <button className="primary" disabled={controller.saving || !relationshipForm.label.trim() || !relationshipForm.source_ref || !relationshipForm.target_ref || relationshipForm.source_ref === relationshipForm.target_ref} onClick={() => void saveRelationship()}><Save /> {controller.saving ? '保存中…' : '保存'}</button>
          </footer>
        </aside>
      )}
    </div>
  )
}
