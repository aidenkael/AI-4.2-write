import { BookOpen, CircleCheck, Compass, FileText, PenLine, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { getProjectOverview, getStoryWriteSurface, type ProjectOverview, type StoryWriteSurface } from '../bridge/client'

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * 作品概览：只展示后端真实数据。
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id）；
 * - 正式状态来自 `getProjectOverview`（work_direction / reader_promise / 有效规划 /
 *   state_rev / last_accepted）；
 * - 写作统计（当前章节号 / 已采用字数）只来自 `getStoryWriteSurface`；
 * - 不展示任何 Mock 状态 / 更新时间 / 简介 / 章节标题 / 字数；
 * - 故事发展 / 故事地图 / 作品资料 / 作品检查 均为真实正式项目页面。
 */
export function ProjectOverviewPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const [overview, setOverview] = useState<ProjectOverview | null>(null)
  const [surface, setSurface] = useState<StoryWriteSurface | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // 当前正式项目 ref：加载期间切换项目时丢弃过期结果，绝不把 A 的概览写进 B
  const projectRef = useRef<string | null>(selected?.project_id ?? null)
  projectRef.current = selected?.project_id ?? null

  const load = useCallback(async () => {
    const pid = selected?.project_id
    if (!pid) return
    setLoading(true)
    setError(null)
    try {
      const [ov, sf] = await Promise.all([
        getProjectOverview(pid),
        getStoryWriteSurface(pid),
      ])
      if (projectRef.current !== pid) return // 加载期间已切换项目 → 丢弃过期结果
      setOverview(ov)
      setSurface(sf)
    } catch (e) {
      if (projectRef.current !== pid) return
      setError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setLoading(false)
    }
  }, [selected])

  useEffect(() => {
    void load()
  }, [load])

  if (!selected) {
    return <div className="empty-state">请先选择正式作品。</div>
  }

  const connectedActions = [
    { label: '故事地图', desc: '查看已确认的人物、关系与事件', Icon: BookOpen, section: 'map' as const },
    { label: '作品资料', desc: '查看正式作品状态投影', Icon: FileText, section: 'data' as const },
    { label: '作品检查', desc: '对选中章节发起一次检查', Icon: CircleCheck, section: 'review' as const },
  ]

  return (
    <div className="project-overview">
      <section className="featured-project panel">
        <div className="featured-art formal-art" />
        <div>
          <div className="title-row">
            <h2>{selected.name}</h2>
            <span className="soft-tag">正式作品</span>
          </div>
          {loading && <p>正在加载正式数据…</p>}
          {error && (
            <div>
              <p className="error-text">{error}</p>
              <button onClick={() => void load()}>
                <RefreshCw />
                重试
              </button>
            </div>
          )}
          {!loading && !error && (
            <>
              {overview?.work_direction && <p>方向：{overview.work_direction}</p>}
              {overview?.reader_promise && <p>读者期待：{overview.reader_promise}</p>}
              <div className="project-stats">
                <span>
                  📖 当前章节
                  <strong>第 {surface?.active_chapter_number ?? 1} 章</strong>
                </span>
                <span>
                  ✎ 已采用字数
                  <strong>{(surface?.total_words ?? 0).toLocaleString()} 字</strong>
                </span>
                <span>
                  ◈ State 版本
                  <strong>{overview?.state?.state_rev != null ? `rev ${overview.state.state_rev}` : '—'}</strong>
                </span>
              </div>
              <div className="overview-plans">
                <strong>当前有效规划</strong>
                {overview?.current_plans && overview.current_plans.length > 0 ? (
                  <ul>
                    {overview.current_plans.map((plan) => (
                      <li key={plan.id}>{plan.description}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted-note">暂无有效规划。</p>
                )}
              </div>
              {overview?.last_accepted && (
                <p className="muted-note">
                  最近已接受：{overview.last_accepted.chapter_path} · {overview.last_accepted.scene_ref}
                </p>
              )}
            </>
          )}
          <div>
            <button className="primary" onClick={() => actions.setProjectSection('writing')}>
              <PenLine />
              继续写作
            </button>
          </div>
        </div>
      </section>
      <div className="overview-actions">
        <button className="panel" onClick={() => actions.setProjectSection('development')}>
          <Compass />
          <span>
            <strong>故事发展</strong>
            <small>一起往前想，规划下一步</small>
          </span>
        </button>
        {connectedActions.map(({ label, desc, Icon, section }) => (
          <button className="panel" key={label} onClick={() => actions.setProjectSection(section)}>
            <Icon />
            <span>
              <strong>{label}</strong>
              <small>{desc}</small>
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
