import { FileText, PenLine, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { getProjectOverview, getStoryWriteSurface, type ProjectOverview, type StoryWriteSurface } from '../bridge/client'

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * 作品概览：仅当前状态与下一步动作（不复制地基/规划/地图明细）。
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id）；
 * - 正式状态来自 `getProjectOverview`（work_direction / reader_promise / 有效规划计数 / last_accepted）；
 * - 当前章节号 / 已采用字数只来自 `getStoryWriteSurface`；
 * - 规划只呈现计数，明细属于故事规划页；人物/关系/事件属于地基/地图；
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
            <div className="project-stats">
              <span>
                当前章节
                <strong>第 {surface?.active_chapter_number ?? 1} 章</strong>
              </span>
              <span>
                已采用字数
                <strong>{(overview?.progress?.actual_words ?? surface?.total_words ?? 0).toLocaleString()} 字</strong>
                {overview?.progress?.target_words != null && <small>目标 {overview.progress.target_words.toLocaleString()} 字</small>}
              </span>
              <span>
                有效规划
                <strong>{planCount} 条</strong>
              </span>
            </div>
            {overview?.settlement && overview.settlement.status !== 'synchronized' && (
              <div className="sync-warning">
                已保存的作者修改尚待整理：{overview.settlement.pending_count} 项待处理，{overview.settlement.failed_count} 项失败。你可以继续创作；需要整理时使用项目栏的「更新作品状态」。
              </div>
            )}
            {planCount > 0 && (
              <p className="muted-note">当前有效规划 {planCount} 条；明细与下一步决定在故事规划中查看。</p>
            )}
            {overview?.last_accepted && (
              <p className="muted-note">
                最近已接受：{overview.last_accepted.chapter_path.split('/').pop()?.replace(/\.md$/, '') ?? overview.last_accepted.chapter_path}
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

      <p className="muted-note overview-footnote">
        <FileText size={14} /> 概览只显示决定下一步所需的信息；明细分别在作品地基、故事规划与故事地图中查看。
      </p>
    </div>
  )
}
