import { Check, FileCheck2, GitBranch, MapPin, Pencil, Plus, Save, Trash2, UserRound, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ProjectDataEntry } from '../bridge/client'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { describeRecord } from '../features/storyMap/storyMapModel'

type FoundationTab = 'characters' | 'relationships' | 'canon_facts' | 'storylines' | 'foreshadowing'
type MaterialState = 'current' | 'future'

const tabs: Array<{ key: FoundationTab; label: string; Icon: typeof UserRound; category: string }> = [
  { key: 'characters', label: '人物', Icon: UserRound, category: 'character' },
  { key: 'relationships', label: '关系', Icon: GitBranch, category: 'relationship' },
  { key: 'canon_facts', label: '世界、地点与势力', Icon: FileCheck2, category: 'world_setting' },
  { key: 'storylines', label: '故事线', Icon: MapPin, category: 'story_line' },
  { key: 'foreshadowing', label: '伏笔与承诺', Icon: Check, category: 'promise_foreshadowing' },
]

const characterFields = [
  ['role', '角色定位'], ['identity', '身份'], ['goal', '目标'], ['motivation', '动机'],
  ['personality', '性格'], ['background', '背景'], ['status', '当前状态'], ['notes', '备注'],
] as const
const defaultFields = [['description', '描述'], ['status', '状态'], ['notes', '备注']] as const

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
  return 'canon_facts'
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
  const handoffRef = useRef<string | null>(null)

  const tabMeta = tabs.find((item) => item.key === tab) ?? tabs[0]
  const entries = useMemo(() => controller.data?.sections[tab] ?? [], [controller.data, tab])
  const fields = tab === 'characters' ? characterFields : defaultFields
  const characters = controller.data?.sections.characters ?? []

  const beginCreate = () => {
    if (tab === 'relationships') {
      setRelationshipForm({
        mode: 'create', ref: null, label: '', source_ref: '', target_ref: '',
        material_state: 'current', description: '', state: '', notes: '', preservedData: {},
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
        description: String(record.description ?? ''), state: String(record.state ?? record.status ?? ''),
        notes: String(record.notes ?? ''),
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
    const sections: FoundationTab[] = ['characters', 'relationships', 'canon_facts', 'storylines', 'foreshadowing']
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
            description: String(record.description ?? ''), state: String(record.state ?? record.status ?? ''),
            notes: String(record.notes ?? ''), preservedData: {},
          })
        } else {
          const entryFields = section === 'characters' ? characterFields : defaultFields
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
      ...(relationshipForm.state.trim() ? { state: relationshipForm.state.trim() } : {}),
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

  return (
    <div className="foundation-page">
      <div className="foundation-direction">
        <section className="panel"><h3>作品方向</h3><p>{controller.data?.work_direction || '当前尚未记录。'}</p></section>
        <section className="panel"><h3>读者期待</h3><p>{controller.data?.reader_promise || '当前尚未记录。'}</p></section>
      </div>

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
          {tab === 'canon_facts' && recordForm.mode === 'create' && (
            <label>记录类型<select value={recordForm.category} onChange={(event) => setRecordForm({ ...recordForm, category: event.target.value })}><option value="world_setting">世界 / 核心设定</option><option value="location">地点</option><option value="organization_force">组织 / 势力</option><option value="custom">自定义系统</option></select></label>
          )}
          <div className="record-fields">
            {fields.map(([key, label]) => (
              <label key={key}>{label}<textarea rows={key === 'background' || key === 'notes' ? 3 : 2} value={recordForm.data[key] ?? ''} onChange={(event) => setRecordForm({ ...recordForm, data: { ...recordForm.data, [key]: event.target.value } })} /></label>
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
