import { FileText, Pencil, PenLine, RefreshCw, Save, Sparkles, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { getProjectOverview, getStoryWriteSurface, updateStorySynopsis, type ProjectOverview, type StoryWriteSurface } from '../bridge/client'
import { impactNoticeText } from '../features/planning/planningImpact'
import { ProjectCoverControl } from '../features/presentation/ProjectCoverControl'

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * 作品概览：仅当前状态与下一步动作（不复制地基/规划/地图明细）。
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id）；
 * - 正式状态来自 `getProjectOverview`（work_direction / reader_promise / 有效规划计数 / last_accepted）；
 * - 当前章节号 / 已采用字数只来自 `getStoryWriteSurface`；
 * - 规划只呈现计数，明细属于大纲与规划页；人物/关系/事件属于地基/地图；
 * - 不展示任何 Mock 状态 / 更新时间 / 简介 / 假进度。
 */
export function ProjectOverviewPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const [overview, setOverview] = useState<ProjectOverview | null>(null)
  const [surface, setSurface] = useState<StoryWriteSurface | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [synopsisOpen, setSynopsisOpen] = useState(false)
  const [synopsisDraft, setSynopsisDraft] = useState('')
  const [savingSynopsis, setSavingSynopsis] = useState(false)
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
      setSynopsisDraft(ov.story_synopsis ?? '')
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
  const visiblePlans = overview?.current_plans?.slice(0, 4) ?? []
  const hiddenPlanCount = Math.max(0, planCount - visiblePlans.length)
  const openItems = overview?.open_items?.items ?? []
  const nextAction = overview?.primary_next_action === 'foundation' ? 'foundation' : 'writing'
  const saveSynopsis = async () => {
    if (!selected || overview?.intent_rev == null) return
    setSavingSynopsis(true)
    setError(null)
    try {
      const result = await updateStorySynopsis({
        project_id: selected.project_id,
        base_intent_rev: overview.intent_rev,
        story_synopsis: synopsisDraft,
      })
      setOverview({ ...overview, intent_rev: result.intent_rev, story_synopsis: result.story_synopsis })
      setSynopsisOpen(false)
      actions.notify('作品简介已保存。')
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setSavingSynopsis(false)
    }
  }
  const runPrimaryAction = () => {
    if (!selected) return
    if (nextAction === 'foundation') {
      actions.setFoundationDesignHandoff({
        project_id: selected.project_id,
        prefill: '请基于当前作品方向，完善这本书真正需要的人物、关系、世界、地点、组织、体系、故事线与伏笔框架；不需要的部分不要强行创建。',
      })
      actions.setProjectSection('foundation')
      return
    }
    actions.setProjectSection('writing')
  }

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
            <ProjectCoverControl projectId={selected.project_id} name={selected.name}/>
            <div className="overview-grid">
              <section className="overview-card overview-position">
                <header>
                  <h3>作品定位</h3>
                  {overview?.intent_rev != null && <button onClick={() => setSynopsisOpen(true)}><Pencil /> 编辑简介</button>}
                </header>
                <p><b>作品简介 / 核心梗概：</b>{overview?.story_synopsis || '尚未记录。'}</p>
                <p><b>作品方向：</b>{overview?.work_direction || '尚未记录。'}</p>
                <p><b>读者期待：</b>{overview?.reader_promise || '尚未记录。'}</p>
              </section>
              <section className="overview-card">
                <h3>当前进度</h3>
                <div className="project-stats">
                  <span>
                    当前章节
                    <strong>第 {overview?.progress?.current_chapter ?? surface?.active_chapter_number ?? 1} 章</strong>
                  </span>
                  <span>
                    已完成字数
                    <strong>{(overview?.progress?.actual_words ?? surface?.total_words ?? 0).toLocaleString()} 字</strong>
                    {overview?.progress?.target_words != null && <small>目标 {overview.progress.target_words.toLocaleString()} 字</small>}
                  </span>
                  <span>
                    有效规划
                    <strong>{planCount} 条</strong>
                  </span>
                </div>
                {overview?.last_accepted && (
                  <p className="muted-note">
                    最近已接受：{overview.last_accepted.chapter_path.split('/').pop()?.replace(/\.md$/, '') ?? overview.last_accepted.chapter_path}
                  </p>
                )}
              </section>
              <section className="overview-card">
                <h3>当前规划摘要</h3>
                {visiblePlans.length > 0 ? (
                  <>
                    <ul className="overview-compact-list">{visiblePlans.map((plan) => <li key={plan.id}>{plan.description}</li>)}</ul>
                    {hiddenPlanCount > 0 && <button onClick={() => actions.setProjectSection('planning')}>还有 {hiddenPlanCount} 条，前往大纲与规划</button>}
                  </>
                ) : <p className="muted-note">还没有已确认规划。</p>}
              </section>
              <section className="overview-card">
                <h3>重要未解决项</h3>
                {openItems.length > 0 ? (
                  <>
                    <ul className="overview-compact-list">{openItems.map((item, index) => <li key={item.id ?? index}><span>{item.kind}</span>{item.title}</li>)}</ul>
                    {(overview?.open_items?.total ?? 0) > openItems.length && <p className="muted-note">共 {overview?.open_items?.total} 项，这里只显示前 {openItems.length} 项。</p>}
                  </>
                ) : <p className="muted-note">当前没有需要特别带着看的未解决项。</p>}
              </section>
            </div>
            {overview?.settlement && overview.settlement.status !== 'synchronized' && (
              <div className="sync-warning">
                已保存的作者修改尚待整理：{overview.settlement.pending_count} 项待处理，{overview.settlement.failed_count} 项失败。你可以继续创作；需要整理时使用项目栏的「更新作品状态」。
              </div>
            )}
            {(() => {
              const impact = overview?.planning_impact
              const impactTotal = (impact?.pending_count ?? 0) + (impact?.deferred_count ?? 0)
              const notice = impactTotal > 0 ? impactNoticeText(impactTotal) : null
              if (!notice) return null
              return (
                <div className="sync-warning">
                  {notice}
                  <button onClick={() => actions.setProjectSection('planning')}>查看影响</button>
                  <button onClick={() => actions.setProjectSection('planning')}>前往重新规划</button>
                </div>
              )
            })()}
          </>
        )}
        <div className="overview-cta">
          <button className="primary" onClick={runPrimaryAction}>
            {nextAction === 'foundation' ? <Sparkles /> : <PenLine />}
            {nextAction === 'foundation' ? '完善作品地基' : '继续正文'}
          </button>
        </div>
      </section>

      <p className="muted-note overview-footnote">
        <FileText size={14} /> 概览只显示决定下一步所需的信息；明细分别在作品地基、大纲与规划与故事地图中查看。
      </p>
      {synopsisOpen && (
        <aside className="record-drawer panel" aria-label="编辑作品简介">
          <header><h2>编辑作品简介</h2><button aria-label="关闭" onClick={() => setSynopsisOpen(false)}><X /></button></header>
          <div className="record-drawer-body">
            <label>作品简介 / 核心梗概<textarea rows={8} value={synopsisDraft} onChange={(event) => setSynopsisDraft(event.target.value)} /></label>
            <p className="muted-note">这里只保存作品级简介；作品方向和读者期待仍由既有创作方向合同维护。</p>
          </div>
          <footer>
            <button onClick={() => setSynopsisOpen(false)}>取消</button>
            <button className="primary" disabled={savingSynopsis} onClick={() => void saveSynopsis()}><Save /> 保存</button>
          </footer>
        </aside>
      )}
    </div>
  )
}
