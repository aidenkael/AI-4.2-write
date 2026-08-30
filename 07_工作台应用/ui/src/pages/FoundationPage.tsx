import { FileCheck2, MapPin, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import type { ProjectDataEntry } from '../bridge/client'

/**
 * 作品地基：当前已确定事实的作者可读投影（只读，零写回、零模型）。
 *
 * - 数据只来自 getProjectData 的当前正式状态：work_direction / reader_promise /
 *   characters / relationships / canon_facts；
 * - 不重复 approved_plan（规划属于故事规划）；occurred_events / open_threads
 *   属于故事地图的消费面，不作为地基主体；
 * - 不提供任意 Canon 编辑（编辑未安全接入，宁可如实只读）；
 * - 空态如实说明"当前尚未记录"，不暗示后端缺失。
 */

type FoundationTab = 'characters' | 'relationships' | 'canon_facts'

const tabs: Array<{ key: FoundationTab; label: string; Icon: typeof UserRound }> = [
  { key: 'characters', label: '人物', Icon: UserRound },
  { key: 'relationships', label: '关系', Icon: MapPin },
  { key: 'canon_facts', label: '已确认设定', Icon: FileCheck2 },
]

// 常见正式字段的作者面标签；未收录的键按原样低调展示（真实数据，不翻译也不隐藏）。
const fieldLabels: Record<string, string> = {
  name: '名称', label: '名称', description: '描述', summary: '概述',
  role: '角色定位', identity: '身份', goal: '目标', motivation: '动机',
  personality: '性格', background: '背景', appearance: '外貌', ability: '能力',
  arc: '人物弧光', status: '当前状态', relation: '关系', relationship: '关系',
  between: '双方', parties: '双方', fact: '事实', content: '内容', note: '备注',
}

function fields(entry: ProjectDataEntry): Array<{ key: string; label: string; value: string }> {
  const record = entry.record
  if (!record || typeof record !== 'object' || Array.isArray(record)) return []
  const out: Array<{ key: string; label: string; value: string }> = []
  for (const [k, v] of Object.entries(record as Record<string, unknown>)) {
    if (k === 'id' || k === 'authority' || k === 'label' || k === 'name') continue
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
      out.push({ key: k, label: fieldLabels[k] ?? k, value: String(v) })
    } else if (Array.isArray(v)) {
      const text = v.filter((x) => typeof x === 'string').join('、')
      if (text) out.push({ key: k, label: fieldLabels[k] ?? k, value: text })
    }
  }
  return out
}

export function FoundationPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useProjectDataController(selected?.project_id ?? null)
  const [tab, setTab] = useState<FoundationTab>('characters')

  const entries = useMemo(() => controller.data?.sections[tab] ?? [], [controller.data, tab])
  const tabLabel = tabs.find((t) => t.key === tab)?.label ?? ''

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
  }

  const data = controller.data

  return (
    <div className="foundation-page">
      <div className="foundation-direction">
        <section className="panel">
          <h3>作品方向</h3>
          {data?.work_direction ? <p>{data.work_direction}</p> : <p className="muted-note">当前尚未记录作品方向。</p>}
        </section>
        <section className="panel">
          <h3>读者期待</h3>
          {data?.reader_promise ? <p>{data.reader_promise}</p> : <p className="muted-note">当前尚未记录读者期待。</p>}
        </section>
      </div>

      <section className="panel foundation-main">
        <header className="foundation-tabs">
          {tabs.map(({ key, label, Icon }) => (
            <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>
              <Icon /> {label}
            </button>
          ))}
        </header>

        {controller.loading && <div className="empty-state">正在加载正式作品数据…</div>}
        {controller.error && <p className="error-text">{controller.error}</p>}

        {!controller.loading && !controller.error && entries.length === 0 && (
          <div className="empty-state">当前尚未记录{tabLabel}。已接受正文与正式决定写入后，会如实出现在这里。</div>
        )}

        <div className="foundation-cards">
          {entries.map((entry) => {
            const fs = fields(entry)
            return (
              <article className="foundation-card" key={`${tab}-${entry.id ?? entry.label}`}>
                <h3>{entry.label || '（未命名条目）'}</h3>
                {fs.length === 0 && <p className="muted-note">暂无更多已记录信息。</p>}
                {fs.map((f) => (
                  <p key={f.key}><b>{f.label}：</b>{f.value}</p>
                ))}
              </article>
            )
          })}
        </div>

        <footer className="foundation-note">
          <p className="muted-note">本页只读展示当前已确定的正式状态；调整方向或事实请通过故事规划确认，不支持在这里直接修改。</p>
          <button onClick={() => actions.setProjectSection('planning')}>去故事规划</button>
        </footer>
      </section>
    </div>
  )
}
