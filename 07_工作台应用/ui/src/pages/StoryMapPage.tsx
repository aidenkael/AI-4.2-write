import { GitBranch, Hourglass, ListTree, Maximize2, Minus, Pencil, RefreshCw, RotateCcw, Plus } from 'lucide-react'
import cytoscape, { type Core } from 'cytoscape'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useApp } from '../features/app/AppStore'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { authorSourceLabel } from '../features/presentation/authorPresentation'
import { AvatarImage } from '../features/presentation/AvatarImage'
import { useProjectPresentation } from '../features/presentation/useProjectPresentation'
import { CharacterEditor, RelationshipEditor } from '../features/foundation/recordEditors'
import type { ProjectDataEntry } from '../bridge/client'
import {
  projectOpenThreads,
  projectRelationshipGraph,
  projectTimeEvents,
  type RecordField,
} from '../features/storyMap/storyMapModel'
import { graphElements, replaceGraphElementData, storyMapStyles } from '../features/storyMap/storyMapCytoscape'

/**
 * 故事地图：同一正式 Story State 的派生可视化/查询面（只读，零写回、零模型）。
 *
 * 三个派生视图（不重复 Foundation 的通用人物/关系卡片列表）：
 * - 人物关系图：Cytoscape 只读图；节点=真实人物记录，边=端点可解析的真实关系记录；
 *   无法形成连线的关系记录如实列在紧凑区块，不猜测、不隐藏；
 * - 时间与事件：只用显式存储的时间锚点；无锚点时保留真实叙事顺序并明确标注；
 * - 未解决线索：open_threads 聚焦视图。
 *
 * 全部解析集中在 features/storyMap/storyMapModel（单一定性投影层）。
 */

type MapTab = 'graph' | 'time' | 'threads'

const tabs: Array<{ key: MapTab; label: string; Icon: typeof GitBranch }> = [
  { key: 'graph', label: '人物关系图', Icon: GitBranch },
  { key: 'time', label: '时间与事件', Icon: Hourglass },
  { key: 'threads', label: '未解决线索', Icon: ListTree },
]

interface SelectedDetail {
  kind: '人物' | '关系'
  label: string
  fields: RecordField[]
  status: 'current' | 'future'
  sourceRef: string | null
  sourceKind: string | null
  editable: boolean
  avatarImageSrc?: string | null
  intro?: string
  role?: string
}

function DetailFields({ fields }: { fields: RecordField[] }) {
  if (fields.length === 0) return <p className="muted-note">暂无更多已记录信息。</p>
  return (
    <>
      {fields.map((f) => (
        <p key={f.key}><b>{f.label}：</b>{f.value}</p>
      ))}
    </>
  )
}

function GroupedCharacterFields({ fields }: { fields: RecordField[] }) {
  const groups = [
    ['当前状态', new Set(['current_state', 'current_objective', 'arc_stage', 'current_location', 'power_rank', 'profession_rank', 'current_level', 'system_level'])],
    ['人物核心', new Set(['persona_core', 'goal_desire', 'fear_weakness', 'inner_conflict', 'values_beliefs', 'visible_traits', 'behavior_anchors', 'speech_style'])],
  ] as const
  const used = new Set<string>()
  const display: Array<{ label: string; values: RecordField[] }> = groups.map(([label, keys]) => {
    const values = fields.filter((field) => keys.has(field.key)); values.forEach((field) => used.add(field.key))
    return { label, values }
  })
  const other = fields.filter((field) => !used.has(field.key) && !['one_line_intro', 'role_identity', 'position_title'].includes(field.key))
  if (other.length) display.push({ label: '背景与其他', values: other })
  return <>{display.filter((group) => group.values.length).map((group) => <section className="map-tooltip-group" key={group.label}><strong>{group.label}</strong>{group.values.map((field) => <small key={field.key}>{field.label}：{field.value}</small>)}</section>)}</>
}

export function StoryMapPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const { presentation } = useProjectPresentation(selected?.project_id ?? null)
  const [tab, setTab] = useState<MapTab>('graph')
  const [detail, setDetail] = useState<SelectedDetail | null>(null)
  const [sharedEditor, setSharedEditor] = useState<{ kind: 'character' | 'relationship'; entry: ProjectDataEntry | null } | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string; avatarImageSrc: string | null; intro: string; role: string; fields: RecordField[] } | null>(null)
  const graphHostRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const graphRef = useRef<ReturnType<typeof projectRelationshipGraph>>({ nodes: [], edges: [], unresolved: [] })
  const sessionPositions = useRef<Record<string, { x: number; y: number }>>({})

  const avatarSources = useMemo(() => Object.fromEntries(Object.entries(presentation?.character_avatars ?? {}).map(([ref, asset]) => [ref, asset.image_src])), [presentation])
  const graph = useMemo(() => projectRelationshipGraph(controller.data, avatarSources), [controller.data, avatarSources])
  graphRef.current = graph
  const timeModel = useMemo(() => projectTimeEvents(controller.data), [controller.data])
  const threads = useMemo(() => projectOpenThreads(controller.data), [controller.data])
  const hasLoadedData = Boolean(selected && controller.data?.project_id === selected.project_id)
  const relationshipCount = controller.data?.sections.relationships.length ?? 0
  const characters = controller.data?.sections.characters ?? []
  const relationshipCharacters = useMemo(
    () => characters.filter((entry) => Boolean(entry.source_ref)),
    [characters],
  )
  const entryForSourceRef = (sourceRef: string | null, kind: 'character' | 'relationship') => {
    if (!sourceRef || !controller.data) return null
    const section = kind === 'character' ? controller.data.sections.characters : controller.data.sections.relationships
    return section.find((entry) => entry.source_ref === sourceRef) ?? null
  }

  // The graph instance lives for one Map/project visit.  Later data changes update
  // elements in place, so a saved author edit cannot discard the dragged positions.
  useEffect(() => {
    return () => { cyRef.current?.destroy(); cyRef.current = null; sessionPositions.current = {} }
  }, [tab, selected?.project_id])

  useEffect(() => {
    if (tab !== 'graph' || graph.nodes.length === 0 || !graphHostRef.current) return
    let cy = cyRef.current
    if (!cy) {
      cy = cytoscape({
        container: graphHostRef.current,
        elements: graphElements(graph),
        style: storyMapStyles as never, wheelSensitivity: 0.6, minZoom: 0.35, maxZoom: 2.2,
      })
      cy.layout({ name: graph.edges.length > 0 ? 'cose' : 'grid', animate: false, fit: true, padding: 36 } as never).run()
      cy.nodes().forEach((node) => { sessionPositions.current[node.id()] = node.position() })
      cy.on('dragfree', 'node', (event) => { sessionPositions.current[event.target.id()] = event.target.position() })
      cy.on('tap', 'node', (event) => {
        const node = graphRef.current.nodes.find((item) => item.id === event.target.id())
        if (node) setDetail({ kind: '人物', label: node.label, fields: node.fields, status: node.status, sourceRef: node.sourceRef, sourceKind: node.sourceKind, editable: node.editable, avatarImageSrc: node.avatarImageSrc, intro: node.intro, role: node.role })
      })
      cy.on('mouseover', 'node', (event) => {
        const node = graphRef.current.nodes.find((item) => item.id === event.target.id())
        if (node) setTooltip({ x: event.renderedPosition.x, y: event.renderedPosition.y, label: node.label, avatarImageSrc: node.avatarImageSrc, intro: node.intro, role: node.role, fields: node.fields })
      })
      cy.on('mousemove', 'node', (event) => setTooltip((current) => current ? { ...current, x: event.renderedPosition.x, y: event.renderedPosition.y } : null))
      cy.on('mouseout', 'node', () => setTooltip(null))
      cy.on('tap', 'edge', (event) => {
        const edge = graphRef.current.edges.find((item) => item.id === event.target.id())
        if (edge) setDetail({ kind: '关系', label: edge.label, fields: edge.fields, status: edge.status, sourceRef: edge.sourceRef, sourceKind: edge.sourceKind, editable: edge.editable })
      })
      cyRef.current = cy
      return
    }
    const wanted = new Map(graphElements(graph).map((element: any) => [element.data.id, element]))
    cy.elements().forEach((element) => { if (!wanted.has(element.id())) element.remove() })
    wanted.forEach((element, id) => {
      const existing = cy?.getElementById(id)
      if (existing && existing.nonempty()) replaceGraphElementData(existing, element.data)
      else cy?.add(element)
    })
    cy.nodes().forEach((node) => {
      const position = sessionPositions.current[node.id()]
      if (position) node.position(position)
      else sessionPositions.current[node.id()] = node.position()
    })
  }, [graph, tab])

  useEffect(() => {
    setDetail(null)
    setTooltip(null)
    setSharedEditor(null)
  }, [tab, selected?.project_id])

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
  }

  const editSource = (sourceRef: string | null, kind?: 'character' | 'relationship') => {
    if (!sourceRef) return
    if (kind) {
      const entry = entryForSourceRef(sourceRef, kind)
      if (entry) {
        setSharedEditor({ kind, entry })
        return
      }
    }
    actions.setFoundationEditHandoff({ project_id: selected.project_id, source_ref: sourceRef })
    actions.setProjectSection('foundation')
  }

  return (
    <div className="panel map-page">
      <header className="map-tabs">
        {tabs.map(({ key, label, Icon }) => (
          <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>
            <Icon /> {label}
          </button>
        ))}
      </header>

      {controller.loading && <div className="empty-state">正在加载正式作品数据…</div>}
      {controller.error && <p className="error-text">{controller.error}</p>}

      {hasLoadedData && tab === 'graph' && (
        <div className="map-graph-wrap">
          <div className="map-graph-main">
            <div className="map-author-actions">
              <button onClick={() => setSharedEditor({ kind: 'character', entry: null })}><Plus /> 新增人物</button>
              <button disabled={relationshipCharacters.length < 2} onClick={() => setSharedEditor({ kind: 'relationship', entry: null })}><Plus /> 新增关系</button>
              {relationshipCharacters.length < 2 && <span className="muted-note">至少需要两位已有稳定记录的人物才能新增关系。</span>}
              {controller.refreshing && <span className="muted-note">正在刷新地图…</span>}
            </div>
            {graph.nodes.length === 0 && (
              <div className="empty-state">当前尚未记录人物。人物与关系在作品地基中确认后，关系图会从这里生成。</div>
            )}
            {graph.nodes.length > 0 && relationshipCount === 0 && (
              <div className="empty-state">已记录 {graph.nodes.length} 位人物，但当前没有关系记录，无法形成连线。</div>
            )}
            {graph.nodes.length > 0 && relationshipCount > 0 && graph.edges.length === 0 && (
              <div className="empty-state">关系记录存在，但双方人物尚未明确；请在下方确认后再生成连线。</div>
            )}
            <div className="map-graph-stage">
              <div ref={graphHostRef} className="map-graph" style={{ display: graph.nodes.length > 0 ? 'block' : 'none' }} />
              {tooltip && <div className="map-tooltip" style={{ left: tooltip.x + 18, top: tooltip.y + 18 }}><AvatarImage src={tooltip.avatarImageSrc} alt=""/><div><strong>{tooltip.label}</strong>{tooltip.intro && <p>{tooltip.intro}</p>}{tooltip.role && <small>{tooltip.role}</small>}<GroupedCharacterFields fields={tooltip.fields}/></div></div>}
            </div>
            {graph.nodes.length > 0 && (
              <div className="map-graph-tools">
                <button onClick={() => cyRef.current?.zoom({ level: Math.min(cyRef.current.zoom() * 1.2, cyRef.current.maxZoom()), renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 } })}><Plus /> 放大</button>
                <button onClick={() => cyRef.current?.zoom({ level: Math.max(cyRef.current.zoom() / 1.2, cyRef.current.minZoom()), renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 } })}><Minus /> 缩小</button>
                <button onClick={() => cyRef.current?.fit(undefined, 24)}><Maximize2 /> 适应视图</button>
                <button onClick={() => { const cy = cyRef.current; if (!cy) return; sessionPositions.current = {}; cy.layout({ name: graph.edges.length > 0 ? 'cose' : 'grid', animate: false, fit: true, padding: 36 } as never).run(); cy.nodes().forEach((node) => { sessionPositions.current[node.id()] = node.position() }) }}><RotateCcw /> 恢复默认布局</button>
                <span className="muted-note">
                  {graph.nodes.length} 人物 · {graph.edges.length} 连线 · 实心为当前、虚线为规划中
                </span>
              </div>
            )}
            {graph.unresolved.length > 0 && (
              <section className="map-unresolved">
                <h3>无法形成连线的关系记录（{graph.unresolved.length}）</h3>
                <ul>
                  {graph.unresolved.map((u) => (
                    <li key={`${u.id}-${u.reason}`}>
                      <strong>{u.label}</strong>
                      <span className={`material-state ${u.status}`}>{u.status === 'future' ? '规划中' : '当前'}</span>
                      <span className="muted-note">{u.reason}</span>
                      {u.editable && <button onClick={() => editSource(u.sourceRef, 'relationship')}><Pencil /> 编辑源记录</button>}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
          <aside className="map-detail">
            {detail ? (
              <>
                <h3>{detail.kind} · {detail.label}</h3>
                {detail.kind === '人物' && <div className="map-character-identity"><AvatarImage src={detail.avatarImageSrc} alt=""/><div>{detail.intro && <p>{detail.intro}</p>}{detail.role && <small>{detail.role}</small>}</div></div>}
                <p><span className={`material-state ${detail.status}`}>{detail.status === 'future' ? '规划中' : '当前'}</span></p>
                <p className="muted-note">{authorSourceLabel(detail.sourceKind)}</p>
                <DetailFields fields={detail.fields} />
                {detail.editable && <button onClick={() => editSource(detail.sourceRef, detail.kind === '人物' ? 'character' : 'relationship')}><Pencil /> 编辑源记录</button>}
              </>
            ) : (
              <p className="muted-note">点击图中人物或连线，查看其真实记录详情。</p>
            )}
          </aside>
        </div>
      )}

      {hasLoadedData && tab === 'time' && (
        <div className="map-time">
          {timeModel.items.length === 0 && (
            <div className="empty-state">当前尚未记录已发生事件。</div>
          )}
          {timeModel.items.length > 0 && !timeModel.hasPreciseAnchors && (
            <p className="muted-note map-time-note">以下事件没有显式时间锚点，仅按真实叙事顺序呈现，不推断日期或时长。</p>
          )}
          {timeModel.items.length > 0 && (
            <ol className="map-timeline">
              {timeModel.items.map((item) => (
                <li key={item.id}>
                  <span className={`map-timeline-dot ${item.anchor ? 'anchored' : ''}`} />
                  <div>
                    {item.anchor && <strong className="map-timeline-anchor">{item.anchor}</strong>}
                    <p>{item.label} <span className={`material-state ${item.status}`}>{item.status === 'future' ? '规划中' : '当前'}</span></p>
                    {!item.anchor && <small className="muted-note">无精确时间锚点 · 叙事顺序 {item.order + 1}</small>}
                    {item.editable && <button onClick={() => editSource(item.sourceRef)}><Pencil /> 到作品地基编辑</button>}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {hasLoadedData && tab === 'threads' && (
        <div className="map-threads">
          {threads.length === 0 && (
            <div className="empty-state">当前没有未解决线索。</div>
          )}
          {threads.map((t) => (
            <article className="map-thread-card" key={t.id}>
              <h3>{t.label}</h3>
              <p><span className={`material-state ${t.status}`}>{t.status === 'future' ? '规划中' : '当前'}</span> · {t.kind === 'foreshadowing' ? '伏笔/承诺' : '未解决线索'}</p>
              <DetailFields fields={t.fields} />
              {t.editable && <button onClick={() => editSource(t.sourceRef)}><Pencil /> 到作品地基编辑</button>}
            </article>
          ))}
        </div>
      )}

      <footer className="map-note">
        <p className="muted-note"><RefreshCw size={13} /> 地图只从当前作品真相生成；人物与关系会打开同一源记录编辑器，本页不保存第二份故事事实。</p>
      </footer>
      {sharedEditor?.kind === 'character' && <CharacterEditor key={sharedEditor.entry?.source_ref ?? 'map-character'} entry={sharedEditor.entry} controller={controller} onClose={() => setSharedEditor(null)} />}
      {sharedEditor?.kind === 'relationship' && <RelationshipEditor key={sharedEditor.entry?.source_ref ?? 'map-relationship'} entry={sharedEditor.entry} characters={relationshipCharacters} controller={controller} onClose={() => setSharedEditor(null)} />}
    </div>
  )
}
