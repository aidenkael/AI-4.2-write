import { BookOpen, ChevronRight, Plus, Save, Target, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ProjectDataController } from '../projectData/useProjectDataController'
import { normalizeChapterForeshadowing } from './planningFields'

interface StageDraft { ref?: string; client_key?: string; title: string; target_words: string; kind: string }
interface ChapterDraft {
  ref?: string
  chapter_number: number
  title: string
  min_words: string
  max_words: string
  task: string
  previous_recap: string
  synopsis: string
  pov: string
  planned_location: string
  planned_time: string
  participating_characters: string
  new_characters: string
  key_beats: string
  key_events: string
  foreshadowing: string
  notes: string
  storyline: string
  conflict: string
  emotional_movement: string
  information_gap: string
  information_release_gap: string
  end_state_hook: string
  stage_ref: string
  stage_unresolved: string
  formal_prose_exists: boolean
  actual_words: number
}
interface PlanningDraftState { total: string; stages: StageDraft[]; chapters: ChapterDraft[] }

const text = (value: unknown) => typeof value === 'string' ? value : ''
const numberText = (value: unknown) => typeof value === 'number' ? String(value) : ''
const listText = (value: unknown) => Array.isArray(value) ? value.filter((item) => typeof item === 'string').join('、') : text(value)
const splitList = (value: string) => value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)

export function PlanningStructure({ controller }: { controller: ProjectDataController }) {
  const [total, setTotal] = useState('')
  const [stages, setStages] = useState<StageDraft[]>([])
  const [chapters, setChapters] = useState<ChapterDraft[]>([])
  const [selectedStage, setSelectedStage] = useState<'all' | 'unassigned' | string>('all')
  const [editingChapter, setEditingChapter] = useState<number | null>(null)
  const baselineRef = useRef<PlanningDraftState>({ total: '', stages: [], chapters: [] })
  const loadedProjectRef = useRef<string | null>(null)
  const allowRefreshRef = useRef(false)

  const draftSignature = useMemo(() => JSON.stringify({ total, stages, chapters }), [chapters, stages, total])
  const dirty = draftSignature !== JSON.stringify(baselineRef.current)

  useEffect(() => {
    const plan = controller.data?.length_plan
    if (!plan) return
    const projectId = controller.data?.project_id ?? null
    const projectChanged = loadedProjectRef.current !== projectId
    if (!projectChanged && dirty && !allowRefreshRef.current) return
    const nextTotal = plan.total_target_words == null ? '' : String(plan.total_target_words)
    const nextStages: StageDraft[] = plan.stages.map((item) => {
      const record = item.record && typeof item.record === 'object' ? item.record as Record<string, unknown> : {}
      return { ref: item.source_ref ?? undefined, title: item.label, target_words: numberText(record.target_words), kind: text(record.kind) }
    })
    const nextChapters = plan.chapters.map((item) => ({
      ref: typeof item.ref === 'string' ? item.ref : undefined,
      chapter_number: item.chapter_number,
      title: text(item.title) || `第${item.chapter_number}章`,
      min_words: numberText(item.min_words), max_words: numberText(item.max_words),
      task: text(item.task), previous_recap: text(item.previous_recap), synopsis: text(item.synopsis),
      pov: text(item.pov), planned_location: text(item.planned_location), planned_time: text(item.planned_time),
      participating_characters: listText(item.participating_characters),
      new_characters: listText(item.new_characters), key_events: listText(item.key_events),
      key_beats: listText(item.key_beats),
      foreshadowing: listText(normalizeChapterForeshadowing(item)), notes: text(item.notes), storyline: text(item.storyline),
      conflict: text(item.conflict), emotional_movement: text(item.emotional_movement),
      information_gap: text(item.information_gap), stage_ref: text(item.stage_ref), stage_unresolved: text(item.stage_unresolved),
      formal_prose_exists: item.formal_prose_exists === true, actual_words: item.actual_words,
      information_release_gap: text(item.information_release_gap),
      end_state_hook: text(item.end_state_hook),
    }))
    baselineRef.current = { total: nextTotal, stages: nextStages, chapters: nextChapters }
    loadedProjectRef.current = projectId
    allowRefreshRef.current = false
    const stageKeys = new Set(nextStages.map((stage) => stage.ref ?? stage.client_key).filter(Boolean))
    setSelectedStage((current) => (
      current === 'all' || current === 'unassigned' || stageKeys.has(current) ? current : 'all'
    ))
    setTotal(nextTotal)
    setStages(nextStages)
    setChapters(nextChapters)
  }, [controller.data?.length_plan, controller.data?.project_id])

  const activeChapter = useMemo(
    () => chapters.find((item) => item.chapter_number === editingChapter) ?? null,
    [chapters, editingChapter],
  )
  const visibleChapters = useMemo(() => chapters.filter((chapter) => {
    if (selectedStage === 'all') return true
    if (selectedStage === 'unassigned') return !chapter.stage_ref
    return chapter.stage_ref === selectedStage
  }), [chapters, selectedStage])

  const updateChapter = (patch: Partial<ChapterDraft>) => {
    if (!activeChapter) return
    setChapters((items) => items.map((item) => item.chapter_number === activeChapter.chapter_number ? { ...item, ...patch } : item))
  }

  const addChapter = () => {
    const next = Math.max(0, ...chapters.map((item) => item.chapter_number)) + 1
    const stageRef = selectedStage !== 'all' && selectedStage !== 'unassigned' ? selectedStage : ''
    setChapters((items) => [...items, {
      chapter_number: next, title: `第${next}章`, min_words: '2500', max_words: '4000',
      task: '', previous_recap: '', synopsis: '', pov: '', planned_location: '', planned_time: '',
      participating_characters: '', new_characters: '', key_beats: '', key_events: '',
      foreshadowing: '', notes: '', storyline: '', conflict: '', emotional_movement: '',
      information_gap: '', information_release_gap: '',
      end_state_hook: '', stage_ref: stageRef, stage_unresolved: '', formal_prose_exists: false, actual_words: 0,
    }])
    setEditingChapter(next)
  }

  const cancelDrafts = () => {
    const baseline = baselineRef.current
    setTotal(baseline.total)
    setStages(baseline.stages.map((item) => ({ ...item })))
    setChapters(baseline.chapters.map((item) => ({ ...item })))
    setEditingChapter(null)
  }

  const save = async () => {
    const totalWords = total.trim() ? Number(total) : null
    const stagePayload = stages.map((item) => ({
      ...(item.ref ? { ref: item.ref } : {}),
      ...(!item.ref && item.client_key ? { client_key: item.client_key } : {}),
      title: item.title.trim(),
      target_words: Number(item.target_words || 0), ...(item.kind.trim() ? { kind: item.kind.trim() } : {}),
    })).filter((item) => item.title)
    const chapterPayload = chapters.filter((item) => item.min_words && item.max_words).map((item) => ({
      ...(item.ref ? { ref: item.ref } : {}), title: item.title.trim() || `第${item.chapter_number}章`,
      chapter_number: item.chapter_number, min_words: Number(item.min_words), max_words: Number(item.max_words),
      chapter_title: item.title.trim(), task: item.task.trim(), previous_recap: item.previous_recap.trim(),
      synopsis: item.synopsis.trim(), pov: item.pov.trim(), planned_location: item.planned_location.trim(),
      planned_time: item.planned_time.trim(), participating_characters: splitList(item.participating_characters),
      new_characters: splitList(item.new_characters), key_beats: splitList(item.key_beats),
      key_events: splitList(item.key_events),
      foreshadowing: splitList(item.foreshadowing), notes: item.notes.trim(), storyline: item.storyline.trim(),
      conflict: item.conflict.trim(), emotional_movement: item.emotional_movement.trim(),
      information_gap: item.information_gap.trim(), information_release_gap: item.information_release_gap.trim(),
      end_state_hook: item.end_state_hook.trim(), stage_key: item.stage_ref || null,
    }))
    allowRefreshRef.current = true
    const ok = await controller.saveLengthPlan({ total_target_words: totalWords, stages: stagePayload, chapter_targets: chapterPayload })
    if (!ok) allowRefreshRef.current = false
  }

  return (
    <section className="panel planning-structure">
      <header className="planning-structure-head">
        <div><h2><Target /> 全书与章节规划</h2><p className="muted-note">总目标 → 可选阶段 → 章节范围 → 正式正文实际字数。阶段结构按作品需要使用，不强制分卷。</p></div>
        <div className="editor-save-actions">
          {dirty && <span className="unsaved-note">未保存</span>}
          <button disabled={!dirty || controller.saving} onClick={cancelDrafts}><X /> 取消修改</button>
          <button className="primary" disabled={!dirty || controller.saving} onClick={() => void save()}><Save /> {controller.saving ? '保存中…' : '保存规划'}</button>
        </div>
      </header>

      <div className="length-overview">
        <label>全书目标字数<input type="number" min="0" value={total} onChange={(event) => setTotal(event.target.value)} placeholder="例如 200000" /></label>
        <div><strong>{controller.data?.length_plan.actual_total_words.toLocaleString() ?? 0}</strong><span>已完成字数</span></div>
        <div><strong>{total ? `${Math.min(100, Math.round(((controller.data?.length_plan.actual_total_words ?? 0) / Number(total)) * 100))}%` : '—'}</strong><span>全书进度</span></div>
      </div>

      <div className="planning-structure-grid">
        <section className="stage-planning">
          <header><h3>卷 / 阶段</h3><button onClick={() => setStages((items) => [...items, { client_key: `stage-${Date.now()}-${items.length}`, title: '', target_words: '', kind: '' }])}><Plus /> 添加</button></header>
          <div className="stage-filter-list">
            <button className={selectedStage === 'all' ? 'active' : ''} onClick={() => setSelectedStage('all')}>全部章节<small>{chapters.length} 章</small></button>
            <button className={selectedStage === 'unassigned' ? 'active' : ''} onClick={() => setSelectedStage('unassigned')}>未分卷<small>{chapters.filter((chapter) => !chapter.stage_ref).length} 章</small></button>
            {stages.filter((stage) => stage.title.trim()).map((stage, index) => {
              const key = stage.ref ?? stage.client_key ?? `stage-${index}`
              return <button key={key} className={selectedStage === key ? 'active' : ''} onClick={() => setSelectedStage(key)}>{stage.title}<small>{chapters.filter((chapter) => chapter.stage_ref === key).length} 章</small></button>
            })}
          </div>
          {stages.length === 0 && <p className="muted-note">可选。作品不需要阶段层级时可以留空。</p>}
          {stages.map((stage, index) => (
            <div className="stage-row" key={stage.ref ?? index}>
              <input aria-label="阶段名称" value={stage.title} onChange={(event) => setStages((items) => items.map((item, i) => i === index ? { ...item, title: event.target.value } : item))} placeholder="第一幕 / 第一卷 / 调查阶段" />
              <input aria-label="阶段字数" type="number" min="0" value={stage.target_words} onChange={(event) => setStages((items) => items.map((item, i) => i === index ? { ...item, target_words: event.target.value } : item))} placeholder="目标字数" />
              <input aria-label="阶段类型" value={stage.kind} onChange={(event) => setStages((items) => items.map((item, i) => i === index ? { ...item, kind: event.target.value } : item))} placeholder="类型（可选）" />
              <button aria-label="删除阶段" onClick={() => setStages((items) => items.filter((_, i) => i !== index))}><Trash2 /></button>
            </div>
          ))}
        </section>

        <section className="chapter-planning">
          <header><h3><BookOpen /> 章节细纲</h3><button onClick={addChapter}><Plus /> 添加章节</button></header>
          <div className="chapter-plan-list">
            {visibleChapters.map((chapter) => (
              <button key={chapter.chapter_number} onClick={() => setEditingChapter(chapter.chapter_number)}>
                <span><strong>{chapter.title}</strong><small>{chapter.task || '尚未填写章节任务'}</small></span>
                <span>{chapter.min_words && chapter.max_words ? `${chapter.min_words}–${chapter.max_words} 字` : '未设目标'}<small>{chapter.formal_prose_exists ? '已有正文' : '仅规划'} · 实际 {chapter.actual_words.toLocaleString()} 字</small></span>
                <ChevronRight />
              </button>
            ))}
            {visibleChapters.length === 0 && <p className="muted-note">当前筛选下还没有章节细纲。</p>}
          </div>
        </section>
      </div>

      {activeChapter && (
        <aside className="record-drawer chapter-outline-drawer panel" aria-label="章节细纲编辑">
          <header><h2>第 {activeChapter.chapter_number} 章细纲</h2><button onClick={() => setEditingChapter(null)}><X /></button></header>
          <div className="record-drawer-body">
            <label>章节标题<input value={activeChapter.title} onChange={(event) => updateChapter({ title: event.target.value })} /></label>
            <label>阶段 / 分卷关联<select value={activeChapter.stage_ref} onChange={(event) => updateChapter({ stage_ref: event.target.value, stage_unresolved: '' })}><option value="">未分卷</option>{stages.filter((stage) => stage.title.trim()).map((stage, index) => { const key = stage.ref ?? stage.client_key ?? `stage-${index}`; return <option key={key} value={key}>{stage.title}</option> })}</select></label>
            {activeChapter.stage_unresolved && <p className="muted-note">旧阶段文本无法唯一匹配，请重新选择阶段或设为未分卷。</p>}
            <div className="two-fields"><label>目标最少字数<input type="number" min="0" value={activeChapter.min_words} onChange={(event) => updateChapter({ min_words: event.target.value })} /></label><label>目标最多字数<input type="number" min="0" value={activeChapter.max_words} onChange={(event) => updateChapter({ max_words: event.target.value })} /></label></div>
            <label>章节任务 / 目的<textarea value={activeChapter.task} onChange={(event) => updateChapter({ task: event.target.value })} /></label>
            <label>上一章回顾<textarea value={activeChapter.previous_recap} onChange={(event) => updateChapter({ previous_recap: event.target.value })} /></label>
            <label>章节梗概<textarea rows={4} value={activeChapter.synopsis} onChange={(event) => updateChapter({ synopsis: event.target.value })} /></label>
            <div className="two-fields"><label>视角（可选）<input value={activeChapter.pov} onChange={(event) => updateChapter({ pov: event.target.value })} /></label><label>故事线<input value={activeChapter.storyline} onChange={(event) => updateChapter({ storyline: event.target.value })} /></label></div>
            <div className="two-fields"><label>规划地点<input value={activeChapter.planned_location} onChange={(event) => updateChapter({ planned_location: event.target.value })} /></label><label>规划时间<input value={activeChapter.planned_time} onChange={(event) => updateChapter({ planned_time: event.target.value })} /></label></div>
            <label>参与人物<input value={activeChapter.participating_characters} onChange={(event) => updateChapter({ participating_characters: event.target.value })} /></label>
            <label>新登场人物<input value={activeChapter.new_characters} onChange={(event) => updateChapter({ new_characters: event.target.value })} /></label>
            <label>关键节拍<input value={activeChapter.key_beats} onChange={(event) => updateChapter({ key_beats: event.target.value })} /></label>
            <label>关键事件<textarea value={activeChapter.key_events} onChange={(event) => updateChapter({ key_events: event.target.value })} /></label>
            <label>伏笔 / 埋设 / 回收<textarea value={activeChapter.foreshadowing} onChange={(event) => updateChapter({ foreshadowing: event.target.value })} /></label>
            <details><summary>更多可选项</summary><label>冲突<input value={activeChapter.conflict} onChange={(event) => updateChapter({ conflict: event.target.value })} /></label><label>情绪移动<input value={activeChapter.emotional_movement} onChange={(event) => updateChapter({ emotional_movement: event.target.value })} /></label><label>信息释放 / 信息差<input value={activeChapter.information_release_gap} onChange={(event) => updateChapter({ information_release_gap: event.target.value })} /></label><label>结束状态 / 钩子<input value={activeChapter.end_state_hook} onChange={(event) => updateChapter({ end_state_hook: event.target.value })} /></label></details>
            <label>作者备注<textarea rows={3} value={activeChapter.notes} onChange={(event) => updateChapter({ notes: event.target.value })} /></label>
          </div>
          <footer><button className="danger" onClick={() => { if (activeChapter.formal_prose_exists && !window.confirm('确认移除章节规划？正式正文会保留，不会删除、归档或重编号。')) return; setChapters((items) => items.filter((item) => item.chapter_number !== activeChapter.chapter_number)); setEditingChapter(null) }}><Trash2 /> {activeChapter.formal_prose_exists ? '移除章节规划（正文保留）' : '删除章节规划'}</button><button onClick={() => setEditingChapter(null)}><X /> 关闭</button><button className="primary" disabled={!dirty || controller.saving} onClick={() => { setEditingChapter(null); void save() }}><Save /> 保存全部规划</button></footer>
        </aside>
      )}
    </section>
  )
}
