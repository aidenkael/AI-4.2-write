import { GitBranch, Hourglass, ListTree, Maximize2, Pencil, RefreshCw } from 'lucide-react'
import cytoscape, { type Core } from 'cytoscape'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useApp } from '../features/app/AppStore'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { authorSourceLabel } from '../features/presentation/authorPresentation'
import {
  projectOpenThreads,
  projectRelationshipGraph,
  projectTimeEvents,
  type RecordField,
} from '../features/storyMap/storyMapModel'

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
  avatarText?: string
  avatarHue?: number
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

export function StoryMapPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [tab, setTab] = useState<MapTab>('graph')
  const [detail, setDetail] = useState<SelectedDetail | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; label: string; avatarText: string; avatarHue: number; intro: string; role: string; fields: RecordField[] } | null>(null)
  const graphHostRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)

  const graph = useMemo(() => projectRelationshipGraph(controller.data), [controller.data])
  const timeModel = useMemo(() => projectTimeEvents(controller.data), [controller.data])
  const threads = useMemo(() => projectOpenThreads(controller.data), [controller.data])
  const relationshipCount = controller.data?.sections.relationships.length ?? 0

  // Cytoscape 只读图：数据或页签变化时重建；离开时销毁，不持有第二套事实。
  useEffect(() => {
    if (tab !== 'graph' || graph.nodes.length === 0 || !graphHostRef.current) return
    const cy = cytoscape({
      container: graphHostRef.current,
      elements: [
        ...graph.nodes.map((n) => ({ data: { id: n.id, label: n.short, status: n.status, avatarColor: `hsl(${n.avatarHue} 72% 72%)` } })),
        ...graph.edges.map((e) => ({ data: { id: e.id, source: e.source, target: e.target, label: e.label, status: e.status } })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': 'data(avatarColor)',
            'background-opacity': 0.9,
            color: '#172545',
            'font-size': 12,
            'text-wrap': 'ellipsis',
            'text-max-width': '120px',
            'text-margin-y': 4,
            'text-valign': 'bottom',
            width: 26,
            height: 26,
          },
        },
        {
          selector: 'node[status = "future"]',
          style: {
            'background-color': '#ffffff',
            'border-color': '#6f91df',
            'border-width': 3,
            'border-style': 'dashed',
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            'line-color': '#8fb1ff',
            'target-arrow-color': '#8fb1ff',
            'target-arrow-shape': 'none',
            'curve-style': 'bezier',
            'font-size': 11,
            color: '#64728f',
            'text-wrap': 'ellipsis',
            'text-max-width': '140px',
          },
        },
        {
          selector: 'edge[status = "future"]',
          style: { 'line-style': 'dashed', 'line-color': '#9aa8c5', color: '#7c89a3' },
        },
        { selector: ':selected', style: { 'overlay-opacity': 0.15, 'overlay-color': '#2868f7' } },
      ],
      wheelSensitivity: 0.2,
      minZoom: 0.4,
      maxZoom: 1.6,
    })
    cy.layout({ name: graph.edges.length > 0 ? 'cose' : 'grid', animate: false, fit: true, padding: 24 } as never).run()
    cy.on('tap', 'node', (event) => {
      const node = graph.nodes.find((n) => n.id === event.target.id())
      if (node) setDetail({
        kind: '人物', label: node.label, fields: node.fields, status: node.status,
        sourceRef: node.sourceRef, sourceKind: node.sourceKind, editable: node.editable,
        avatarText: node.avatarText, avatarHue: node.avatarHue, intro: node.intro, role: node.role,
      })
    })
    cy.on('mouseover', 'node', (event) => {
      const node = graph.nodes.find((item) => item.id === event.target.id())
      const position = event.renderedPosition
      if (node) setTooltip({ x: position.x, y: position.y, label: node.label, avatarText: node.avatarText, avatarHue: node.avatarHue, intro: node.intro, role: node.role, fields: node.hoverFields })
    })
    cy.on('mousemove', 'node', (event) => setTooltip((current) => current ? { ...current, x: event.renderedPosition.x, y: event.renderedPosition.y } : null))
    cy.on('mouseout', 'node', () => setTooltip(null))
    cy.on('tap', 'edge', (event) => {
      const edge = graph.edges.find((e) => e.id === event.target.id())
      if (edge) setDetail({
        kind: '关系', label: edge.label, fields: edge.fields, status: edge.status,
        sourceRef: edge.sourceRef, sourceKind: edge.sourceKind, editable: edge.editable,
      })
    })
    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [graph, tab])

  useEffect(() => {
    setDetail(null)
    setTooltip(null)
  }, [tab, selected?.project_id])

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
  }

  const editSource = (sourceRef: string | null) => {
    if (!sourceRef) return
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

      {!controller.loading && !controller.error && tab === 'graph' && (
        <div className="map-graph-wrap">
          <div className="map-graph-main">
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
              {tooltip && <div className="map-tooltip" style={{ left: tooltip.x + 18, top: tooltip.y + 18 }}><span className="character-avatar" style={{ '--avatar-hue': tooltip.avatarHue } as CSSProperties}>{tooltip.avatarText}</span><strong>{tooltip.label}</strong>{tooltip.intro && <p>{tooltip.intro}</p>}{tooltip.role && <small>{tooltip.role}</small>}{tooltip.fields.map((field) => <small key={field.key}>{field.label}：{field.value}</small>)}</div>}
            </div>
            {graph.nodes.length > 0 && (
              <div className="map-graph-tools">
                <button onClick={() => cyRef.current?.fit(undefined, 24)}><Maximize2 /> 适应视图</button>
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
                      {u.editable && <button onClick={() => editSource(u.sourceRef)}><Pencil /> 到作品地基编辑</button>}
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
                {detail.kind === '人物' && <div className="map-character-identity">{detail.avatarText && <span className="character-avatar" style={{ '--avatar-hue': detail.avatarHue ?? 0 } as CSSProperties}>{detail.avatarText}</span>}<div>{detail.intro && <p>{detail.intro}</p>}{detail.role && <small>{detail.role}</small>}</div></div>}
                <p><span className={`material-state ${detail.status}`}>{detail.status === 'future' ? '规划中' : '当前'}</span></p>
                <p className="muted-note">{authorSourceLabel(detail.sourceKind)}</p>
                <DetailFields fields={detail.fields} />
                {detail.editable && <button onClick={() => editSource(detail.sourceRef)}><Pencil /> 到作品地基编辑</button>}
              </>
            ) : (
              <p className="muted-note">点击图中人物或连线，查看其真实记录详情。</p>
            )}
          </aside>
        </div>
      )}

      {!controller.loading && !controller.error && tab === 'time' && (
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

      {!controller.loading && !controller.error && tab === 'threads' && (
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
        <p className="muted-note"><RefreshCw size={13} /> 地图只从当前作品真相生成；所有修改都在作品地基完成，本页不保存第二份故事事实。</p>
      </footer>
    </div>
  )
}
