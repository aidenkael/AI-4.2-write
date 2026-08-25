import { Compass, FileCheck2, Globe2, MapPin, Search, Star, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import type { ProjectDataEntry, ProjectDataSections } from '../bridge/client'

type CategoryKey = keyof ProjectDataSections

const categories: Array<{ key: CategoryKey; label: string; Icon: typeof UserRound }> = [
  { key: 'characters', label: '人物', Icon: UserRound },
  { key: 'relationships', label: '关系', Icon: MapPin },
  { key: 'canon_facts', label: '已确认设定', Icon: FileCheck2 },
  { key: 'occurred_events', label: '重要事件', Icon: Star },
  { key: 'open_threads', label: '未解决线索', Icon: Globe2 },
  { key: 'approved_plan', label: '已确认规划', Icon: Compass },
]

function renderRecord(entry: ProjectDataEntry): Array<{ key: string; value: string }> {
  const record = entry.record
  if (!record || typeof record !== 'object' || Array.isArray(record)) return []
  const fields: Array<{ key: string; value: string }> = []
  for (const [k, v] of Object.entries(record as Record<string, unknown>)) {
    if (k === 'id' || k === 'authority') continue
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      fields.push({ key: k, value: String(v) })
    } else if (Array.isArray(v)) {
      const text = v.filter((x) => typeof x === 'string').join('、')
      if (text) fields.push({ key: k, value: text })
    }
  }
  return fields
}

/**
 * 作品资料：只读正式 Story State 投影。
 *
 * - 数据来自 getProjectData（真实 Story State），零写回、零模型；
 * - 不实现任意 Canon 编辑；改方向/事实请到「故事发展」。
 */
export function ProjectDataPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [cat, setCat] = useState<CategoryKey>('characters')
  const [query, setQuery] = useState('')

  const entries = useMemo(() => {
    const list = controller.data?.sections[cat] ?? []
    const q = query.trim()
    if (!q) return list
    return list.filter((e) => e.label.includes(q) || JSON.stringify(e.record).includes(q))
  }, [controller.data, cat, query])

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
  }

  return (
    <div className="data-layout">
      <aside className="panel data-menu">
        {categories.map(({ key, label, Icon }) => (
          <button key={key} className={cat === key ? 'active' : ''} onClick={() => { setCat(key); setQuery('') }}>
            <Icon /> {label}
          </button>
        ))}
        <div className="muted-note">只读投影，来自正式作品状态。</div>
      </aside>

      <section className="panel data-main">
        <header>
          <h2>{categories.find((c) => c.key === cat)?.label} <small>共 {entries.length} 项</small></h2>
          <label>
            <Search />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索…" />
          </label>
        </header>

        {controller.loading && <div className="empty-state">正在加载正式作品数据…</div>}
        {controller.error && <p className="error-text">{controller.error}</p>}

        {!controller.loading && !controller.error && entries.length === 0 && (
          <div className="empty-state">暂无{categories.find((c) => c.key === cat)?.label}条目。</div>
        )}

        {entries.map((entry) => (
          <article className="record-item" key={`${cat}-${entry.id ?? entry.label}`}>
            <div>
              <h2>{entry.label || '（未命名条目）'}</h2>
              {renderRecord(entry).map((f) => (
                <p key={f.key}><b>{f.key}：</b>{f.value}</p>
              ))}
            </div>
          </article>
        ))}

        <footer className="data-note">
          <p className="muted-note">需要改变故事方向或事实？到「故事发展」确认新的方向，而不是直接改这里。</p>
          <button onClick={() => actions.setProjectSection('development')}>
            <Compass /> 去故事发展
          </button>
        </footer>
      </section>
    </div>
  )
}
