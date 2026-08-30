import { BookOpen, CircleCheck, Compass, FileText, Layers, PenLine, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { getProjectOverview, getStoryWriteSurface, type ProjectOverview, type StoryWriteSurface } from '../bridge/client'

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * 作品概览：紧凑的作品首页，回答"这本书现在到哪里，我接下来做什么？"
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id）；
 * - 正式状态来自 `getProjectOverview`（work_direction / reader_promise / 有效规划 / last_accepted）；
 * - 当前章节号 / 已采用字数只来自 `getStoryWriteSurface`；
 * - 不复制人物 / 关系 / 事件 / 地基记录 / 完整规划 / 检查指标等明细（各有专属页面）；
 * - 不展示任何 Mock 状态 / 更新时间 / 简介 / 假进度。
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

  const planCount = overview?.current_plans?.length ?? 0

  const nextActions = [
    { label: '正在写', desc: '继续写当前章节的正文', Icon: PenLine, section: 'writing' as const },
    { label: '故事规划', desc: '和 AI 一起决定接下来的方向', Icon: Compass, section: 'planning' as const },
    { label: '作品地基', desc: '查看已确定的人物、关系与核心事实', Icon: Layers, section: 'foundation' as const },
    { label: '故事地图', desc: '查看已经发生了什么、线索在哪里', Icon: BookOpen, section: 'map' as const },
    { label: '作品检查', desc: '对选中章节发起一次检查', Icon: CircleCheck, section: 'review' as const },
  ]

  return (
    <div className="overview-page">
      <section className="panel overview-status">
        {loading && <p className="muted-note">正在加载正式数据…</p>}
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
            <div className="overview-facts">
              <div>
                <h3>作品方向</h3>
                {overview?.work_direction ? <p>{overview.work_direction}</p> : <p className="muted-note">当前尚未记录。</p>}
              </div>
              <div>
                <h3>读者期待</h3>
                {overview?.reader_promise ? <p>{overview.reader_promise}</p> : <p className="muted-note">当前尚未记录。</p>}
              </div>
            </div>
            <div className="project-stats">
              <span>
                当前章节
                <strong>第 {surface?.active_chapter_number ?? 1} 章</strong>
              </span>
              <span>
                已采用字数
                <strong>{(surface?.total_words ?? 0).toLocaleString()} 字</strong>
              </span>
              <span>
                有效规划
                <strong>{planCount} 条</strong>
              </span>
            </div>
            {planCount > 0 && (
              <div className="overview-plans">
                <strong>当前有效规划</strong>
                <ul>
                  {overview!.current_plans!.map((plan) => (
                    <li key={plan.id}>{plan.description}</li>
                  ))}
                </ul>
              </div>
            )}
            {overview?.last_accepted && (
              <p className="muted-note">
                最近已接受：{overview.last_accepted.chapter_path} · {overview.last_accepted.scene_ref}
              </p>
            )}
          </>
        )}
        <div className="overview-cta">
          <button className="primary" onClick={() => actions.setProjectSection('writing')}>
            <PenLine />
            继续写作
          </button>
        </div>
      </section>

      <div className="overview-actions">
        {nextActions.map(({ label, desc, Icon, section }) => (
          <button className="panel" key={label} onClick={() => actions.setProjectSection(section)}>
            <Icon />
            <span>
              <strong>{label}</strong>
              <small>{desc}</small>
            </span>
          </button>
        ))}
      </div>

      <p className="muted-note overview-footnote">
        <FileText size={14} /> 概览只显示决定下一步所需的信息；明细分别在作品地基、故事规划与故事地图中查看。
      </p>
    </div>
  )
}
