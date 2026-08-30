import { Globe2, MapPin, Star, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'

type MapTab = 'characters' | 'relationships' | 'occurred_events' | 'open_threads'

const tabs: Array<{ key: MapTab; label: string; Icon: typeof UserRound }> = [
  { key: 'characters', label: '人物', Icon: UserRound },
  { key: 'relationships', label: '关系', Icon: MapPin },
  { key: 'occurred_events', label: '事件', Icon: Star },
  { key: 'open_threads', label: '未解决线索', Icon: Globe2 },
]

function summary(entry: { id: string | null; label: string; record: unknown }): string {
  if (!entry.label) return ''
  const record = entry.record
  if (record && typeof record === 'object' && !Array.isArray(record)) {
    const extra: string[] = []
    for (const [k, v] of Object.entries(record as Record<string, unknown>)) {
      if (k === 'id' || k === 'authority' || k === 'label') continue
      if (typeof v === 'string' && v && v !== entry.label) extra.push(v)
    }
    if (extra.length) return `${entry.label} — ${extra.slice(0, 2).join('；')}`
  }
  return entry.label
}

/**
 * 故事地图：真实只读投影（与作品地基共用同一正式数据面，不建第二事实库）。
 *
 * - 只展示真正属于地图的数据：人物 / 关系 / 已发生事件 / 未解决线索；
 *   已确认规划属于故事规划页，不在这里重复；
 * - 绝不编造关系边 / 日期 / 地点 / 角色定位 / 时间线 / 伏笔连线；
 * - 若关系条目不足以画图，就如实以卡片/列表呈现，不伪造网络图。
 */
export function StoryMapPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [tab, setTab] = useState<MapTab>('characters')

  const entries = useMemo(() => controller.data?.sections[tab] ?? [], [controller.data, tab])

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
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

      {!controller.loading && !controller.error && entries.length === 0 && (
        <div className="empty-state">暂无{tabs.find((t) => t.key === tab)?.label}条目。</div>
      )}

      <section className="map-overview">
        {entries.map((entry) => (
          <button className="map-overview-card" key={`${tab}-${entry.id ?? entry.label}`} onClick={() => actions.openDialog(entry.label || '条目', summary(entry) || '（无更多信息）')}>
            <strong>{entry.label || '（未命名条目）'}</strong>
            <span>{summary(entry)}</span>
          </button>
        ))}
      </section>

      <footer className="map-note">
        <p className="muted-note">地图只显示已确认的正式状态；没有结构化关系信息时如实以列表呈现，不虚构连线、日期或时间线。</p>
      </footer>
    </div>
  )
}
