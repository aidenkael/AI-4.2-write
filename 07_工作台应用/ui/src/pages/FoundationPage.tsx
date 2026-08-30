import { FileCheck2, MapPin, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { describeRecord } from '../features/storyMap/storyMapModel'

/**
 * 作品地基：当前已确定事实的作者可读源表示（只读，零写回、零模型）。
 *
 * - 数据只来自 getProjectData 的当前正式状态：work_direction / reader_promise /
 *   characters / relationships / canon_facts；
 * - 不重复 approved_plan（规划属于故事规划）；occurred_events / open_threads
 *   属于故事地图的消费面，不作为地基主体；
 * - 不提供任意 Canon 编辑（编辑未安全接入，宁可如实只读）；
 * - 字段描述规则与故事地图共用 storyMapModel.describeRecord（单一投影层）；
 * - 空态如实说明"当前尚未记录"，不暗示后端缺失。
 */

type FoundationTab = 'characters' | 'relationships' | 'canon_facts'

const tabs: Array<{ key: FoundationTab; label: string; Icon: typeof UserRound }> = [
  { key: 'characters', label: '人物', Icon: UserRound },
  { key: 'relationships', label: '关系', Icon: MapPin },
  { key: 'canon_facts', label: '已确认设定', Icon: FileCheck2 },
]

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
            const fs = describeRecord(entry)
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
