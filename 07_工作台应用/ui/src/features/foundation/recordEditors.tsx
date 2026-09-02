import { Image, Plus, RotateCcw, Save, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { pickAndSetPresentation, resetCharacterAvatar, type ProjectDataEntry } from '../../bridge/client'
import type { ProjectDataController } from '../projectData/useProjectDataController'
import { isInternalAuthorField } from '../presentation/authorPresentation.js'
import { AvatarImage } from '../presentation/AvatarImage'
import { useProjectPresentation } from '../presentation/useProjectPresentation'
import { RelationSelector } from './RelationSelector'
import {
  initializeRelationSelections,
  legacyFieldsToStrip,
  LEGACY_RELATION_FIELD_KEYS,
  relationOptions,
  relationSelections,
  stripLegacyRelationFields,
  RELATION_SPECS_BY_SOURCE_CATEGORY,
} from './relationSelectors'

type MaterialState = 'current' | 'future'

export const CHARACTER_EDITOR_FIELDS = [
  ['aliases', '别名'], ['one_line_intro', '一句话介绍'], ['visible_traits', '特征'],
  ['persona_core', '人设'], ['role_identity', '身份 / 角色'], ['position_title', '职位'],
  ['background_summary', '背景'], ['power_rank', '武力 / 等级'], ['current_level', '当前体系等级'],
  ['current_state', '当前状态'], ['current_objective', '当前目标'], ['arc_stage', '人物弧阶段'],
  ['speech_style', '说话特点'], ['behavior_anchors', '行为特点'], ['goal_desire', '目标 / 欲望'],
  ['fear_weakness', '恐惧 / 弱点'], ['inner_conflict', '内在冲突'],
  ['secrets', '秘密'], ['notes', '备注'],
] as const

export function recordObject(entry: ProjectDataEntry | null): Record<string, unknown> {
  return entry?.record && typeof entry.record === 'object' && !Array.isArray(entry.record)
    ? entry.record as Record<string, unknown>
    : {}
}

const injected = new Set(['id', 'name', 'label', 'source', 'target', 'source_name', 'target_name', 'relationship'])
const defaultCharacterListFields = new Set(['aliases', 'visible_traits', 'behavior_anchors'])
const relationshipEndpointFields = new Set(['targets', 'characters', 'between', 'participants', 'source', 'target', 'from', 'to'])

export function splitEditorData(
  entry: ProjectDataEntry | null,
  knownFields: readonly (readonly [string, string])[],
) {
  const record = recordObject(entry)
  const known = new Set(knownFields.map(([key]) => key))
  const knownListFields = new Set<string>()
  const values = Object.fromEntries(knownFields.map(([key]) => {
    const value = record[key]
    if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
      knownListFields.add(key)
      return [key, value.join('、')]
    }
    return [key, typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '']
  }))
  const custom: Array<{ key: string; value: string; isList: boolean }> = []
  const preserved: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(record)) {
    if (known.has(key) || injected.has(key)) continue
    if (isInternalAuthorField(key) || (value && typeof value === 'object' && !Array.isArray(value))) {
      preserved[key] = value
    } else if (LEGACY_RELATION_FIELD_KEYS.has(key)) {
      // 遗留关系文本由关联选择器接管：保留原值，但绝不落入“自定义字段”编辑区。
      preserved[key] = value
    } else if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
      custom.push({ key, value: value.join('、'), isList: true })
    } else if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      custom.push({ key, value: String(value), isList: false })
    }
  }
  return { values, custom, preserved, knownListFields }
}

export function relationshipEndpointRefs(record: Record<string, unknown>, characters: ProjectDataEntry[]): [string, string] {
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

export function CharacterEditor({
  entry, controller, onClose,
}: {
  entry: ProjectDataEntry | null
  controller: ProjectDataController
  onClose(): void
}) {
  const split = useMemo(() => splitEditorData(entry, CHARACTER_EDITOR_FIELDS), [entry])
  const [title, setTitle] = useState(entry?.label ?? '')
  const [materialState, setMaterialState] = useState<MaterialState>(entry?.status === 'future' ? 'future' : 'current')
  const [values, setValues] = useState<Record<string, string>>(split.values)
  const [custom, setCustom] = useState(split.custom)
  const projectData = controller.data
  const { presentation, reload: reloadPresentation } = useProjectPresentation(projectData?.project_id ?? null)
  const orgOptions = useMemo(() => relationOptions(projectData, ['organization_force']), [projectData])
  const systemOptions = useMemo(() => relationOptions(projectData, ['system']), [projectData])
  const relationInit = useMemo(() => initializeRelationSelections({
    category: 'character', sourceRef: entry?.source_ref ?? null,
    record: recordObject(entry), data: projectData,
  }), [entry, projectData])
  const [orgSelection, setOrgSelection] = useState<string[]>(
    relationInit.selections['character_affiliated_with_organization'] ?? [],
  )
  const [systemSelection, setSystemSelection] = useState<string[]>(
    relationInit.selections['character_uses_system'] ?? [],
  )
  const save = async () => {
    if (!title.trim()) return
    let data: Record<string, unknown> = {
      ...split.preserved,
    }
    Object.entries(values).forEach(([key, value]) => {
      if (!value.trim()) return
      data[key] = split.knownListFields.has(key) || defaultCharacterListFields.has(key)
        ? value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
        : value.trim()
    })
    custom.forEach((field) => {
      const key = field.key.trim()
      if (!key || !field.value.trim()) return
      data[key] = field.isList
        ? field.value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
        : field.value.trim()
    })
    const selections = {
      character_affiliated_with_organization: orgSelection,
      character_uses_system: systemSelection,
    }
    // 作者已保存规范化组织选择后，停止写回重复的遗留文本字段。
    data = stripLegacyRelationFields(data, legacyFieldsToStrip('character', selections))
    const relations = relationSelections(selections)
    const ok = entry?.source_ref
      ? await controller.updateFoundation({ ref: entry.source_ref, title: title.trim(), material_state: materialState, data, relations })
      : await controller.createFoundation({ category: 'character', title: title.trim(), material_state: materialState, data, relations })
    if (ok) onClose()
  }
  const retire = async () => {
    if (!entry?.source_ref || !window.confirm(`确认退役人物“${entry.label}”？记录会保留历史，不会直接删除。`)) return
    if (await controller.retireFoundation(entry.source_ref)) onClose()
  }
  const specs = RELATION_SPECS_BY_SOURCE_CATEGORY.character
  const avatar = entry?.source_ref ? presentation?.character_avatars[entry.source_ref] : null
  const updateAvatar = async () => {
    if (!entry?.source_ref || !projectData?.project_id) return
    await pickAndSetPresentation({ target: 'avatar', project_id: projectData.project_id, source_ref: entry.source_ref })
    await reloadPresentation()
  }
  const resetAvatar = async () => {
    if (!entry?.source_ref || !projectData?.project_id) return
    await resetCharacterAvatar(projectData.project_id, entry.source_ref)
    await reloadPresentation()
  }
  return (
    <aside className="record-drawer panel" aria-label={`${entry ? '编辑' : '新增'}人物`}>
      <header><h2>{entry ? '编辑' : '新增'}人物</h2><button onClick={onClose}><X /></button></header>
      <div className="record-drawer-body">
      {entry?.source_ref && <section className="presentation-control"><AvatarImage src={avatar?.image_src} alt="人物头像"/><div><strong>人物头像</strong><p className="muted-note">仅用于展示，不会修改人物资料或触发 AI。</p><button onClick={() => void updateAvatar()}><Image /> 上传 / 更换头像</button><button onClick={() => void resetAvatar()}><RotateCcw /> 恢复默认头像</button></div></section>}
      <label>姓名<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <label>状态<select value={materialState} onChange={(event) => setMaterialState(event.target.value as MaterialState)}><option value="current">当前</option><option value="future">规划中</option></select></label>
      <RelationSelector
        label={specs[0].label}
        options={orgOptions}
        selected={orgSelection}
        onChange={setOrgSelection}
        excludeSelf={entry?.source_ref ?? null}
      />
      <RelationSelector
        label={specs[1].label}
        options={systemOptions}
        selected={systemSelection}
        onChange={setSystemSelection}
        excludeSelf={entry?.source_ref ?? null}
      />
      {relationInit.hints.map((hint) => <p className="muted-note legacy-relation-hint" key={hint.field}>{hint.text}</p>)}
      <div className="record-fields">
        {CHARACTER_EDITOR_FIELDS.map(([key, label]) => <label key={key}>{label}<textarea rows={['background_summary', 'notes'].includes(key) ? 3 : 2} value={values[key] ?? ''} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>)}
        {custom.map((field, index) => <div className="custom-field-row" key={`${field.key}-${index}`}><input aria-label="自定义字段名" value={field.key} onChange={(event) => setCustom(custom.map((item, i) => i === index ? { ...item, key: event.target.value } : item))} /><textarea aria-label="自定义字段值" value={field.value} onChange={(event) => setCustom(custom.map((item, i) => i === index ? { ...item, value: event.target.value } : item))} /><button onClick={() => setCustom(custom.filter((_, i) => i !== index))}><Trash2 /></button></div>)}
        <button onClick={() => setCustom([...custom, { key: '', value: '', isList: false }])}><Plus /> 添加自定义字段</button>
      </div>
      </div>
      <footer>{entry && <button className="danger" onClick={() => void retire()}><Trash2 /> 退役</button>}<button className="primary" disabled={controller.saving || !title.trim()} onClick={() => void save()}><Save /> 保存</button></footer>
    </aside>
  )
}

export function RelationshipEditor({
  entry, characters, controller, onClose,
}: {
  entry: ProjectDataEntry | null
  characters: ProjectDataEntry[]
  controller: ProjectDataController
  onClose(): void
}) {
  const record = useMemo(() => recordObject(entry), [entry])
  const endpoints = useMemo(() => relationshipEndpointRefs(record, characters), [characters, record])
  const [label, setLabel] = useState(entry?.label ?? '')
  const [sourceRef, setSourceRef] = useState(endpoints[0])
  const [targetRef, setTargetRef] = useState(endpoints[1])
  const [materialState, setMaterialState] = useState<MaterialState>(entry?.status === 'future' ? 'future' : 'current')
  const keys = ['description', 'current_state', 'relationship_phase', 'key_history', 'current_tension', 'hidden_information', 'trust', 'closeness', 'notes'] as const
  const relationshipStateKey = Object.prototype.hasOwnProperty.call(record, 'current_state') ? 'current_state'
    : Object.prototype.hasOwnProperty.call(record, 'state') ? 'state' : 'current_state'
  const [values, setValues] = useState<Record<string, string>>(Object.fromEntries(keys.map((key) => {
    const storageKey = key === 'current_state' ? relationshipStateKey : key
    const value = record[storageKey]
    return [key, typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '']
  })))
  const preserved = useMemo(() => {
    const editable = new Set<string>(keys)
    editable.add('state')
    return Object.fromEntries(Object.entries(record).filter(([key]) => (
      !editable.has(key) && !injected.has(key) && !relationshipEndpointFields.has(key)
    )))
  }, [record])
  const labels: Record<(typeof keys)[number], string> = { description: '描述', current_state: '当前关系状态', relationship_phase: '关系阶段', key_history: '关键经历', current_tension: '当前张力', hidden_information: '隐瞒的信息', trust: '信任（可选）', closeness: '亲近（可选）', notes: '备注' }
  const save = async () => {
    if (!label.trim() || !sourceRef || !targetRef || sourceRef === targetRef) return
    const data: Record<string, unknown> = { ...preserved }
    Object.entries(values).forEach(([key, value]) => {
      if (!value.trim()) return
      data[key === 'current_state' ? relationshipStateKey : key] = value.trim()
    })
    const input = { source_ref: sourceRef, target_ref: targetRef, label: label.trim(), material_state: materialState, data }
    const ok = entry?.source_ref
      ? await controller.updateRelationship({ ref: entry.source_ref, ...input })
      : await controller.createRelationship(input)
    if (ok) onClose()
  }
  const retire = async () => {
    if (!entry?.source_ref || !window.confirm(`确认退役关系“${entry.label}”？记录会保留历史，不会直接删除。`)) return
    if (await controller.retireRelationship(entry.source_ref)) onClose()
  }
  return (
    <aside className="record-drawer panel" aria-label={`${entry ? '编辑' : '新增'}关系`}>
      <header><h2>{entry ? '编辑' : '新增'}关系</h2><button onClick={onClose}><X /></button></header>
      <div className="record-drawer-body">
      <label>关系名称 / 类型<input value={label} onChange={(event) => setLabel(event.target.value)} /></label>
      <div className="relationship-endpoints"><label>人物 A<select value={sourceRef} onChange={(event) => setSourceRef(event.target.value)}><option value="">请选择</option>{characters.map((character) => <option key={character.source_ref ?? character.id ?? character.label} value={character.source_ref ?? ''}>{character.label}</option>)}</select></label><label>人物 B<select value={targetRef} onChange={(event) => setTargetRef(event.target.value)}><option value="">请选择</option>{characters.map((character) => <option key={character.source_ref ?? character.id ?? character.label} value={character.source_ref ?? ''}>{character.label}</option>)}</select></label></div>
      <label>状态<select value={materialState} onChange={(event) => setMaterialState(event.target.value as MaterialState)}><option value="current">当前</option><option value="future">规划中</option></select></label>
      {keys.map((key) => <label key={key}>{labels[key]}<textarea rows={['description', 'key_history', 'notes'].includes(key) ? 3 : 2} value={values[key] ?? ''} onChange={(event) => setValues({ ...values, [key]: event.target.value })} /></label>)}
      </div>
      <footer>{entry && <button className="danger" onClick={() => void retire()}><Trash2 /> 退役</button>}<button className="primary" disabled={controller.saving || !label.trim() || !sourceRef || !targetRef || sourceRef === targetRef} onClick={() => void save()}><Save /> 保存</button></footer>
    </aside>
  )
}
