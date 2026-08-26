import { CheckCircle2, FolderOpen, Search, ShieldCheck, Sparkles, TriangleAlert, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useReviewController } from '../features/review/useReviewController'

const severityMeta = {
  priority: { label: '优先处理', Icon: TriangleAlert, cls: 'priority' },
  watch: { label: '值得看看', Icon: Sparkles, cls: 'watch' },
} as const

/**
 * 作品检查：真实、显式、范围受控的 AI 检查。
 *
 * - 页面加载只读（确定性检查面），零模型；
 * - 只有作者按下"开始检查"才发起一次 Agent 检查（默认最新已接受章节）；
 * - 报告非权威、零写回；不提供"标记已处理"持久化；
 * - "检查这段"章节交接：消费一次并选中该章节（项目匹配且章节仍有效时），
 *   绝不自动运行。
 */
export function ReviewPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const controller = useReviewController(selected?.project_id ?? null)
  const { surface, surfaceLoading, surfaceError, report, status, error, selectedChapter, execution } = controller

  // 一次性章节交接（"检查这段"）：项目匹配且章节仍有效才选中，消费即清
  const handoffConsumedRef = useRef(false)
  useEffect(() => {
    if (handoffConsumedRef.current) return
    if (!selected) return
    const handoff = actions.consumeReviewChapterHandoff()
    if (handoff && handoff.project_id === selected.project_id) {
      handoffConsumedRef.current = true
      const valid = surface?.chapters.some((c) => c.chapter_number === handoff.chapter_number)
      if (valid) controller.selectChapter(handoff.chapter_number)
    }
  }, [selected, surface, actions, controller])

  if (!selected) {
    return (
      <div className="empty-state">
        <p>请先在「我的作品」中选择一部正式作品。</p>
        <button className="primary" onClick={() => actions.navigate('projects')}>
          <FolderOpen /> 返回作品列表
        </button>
      </div>
    )
  }

  const running = status === 'running'
  const priorityCount = report?.issues.filter((i) => i.severity === 'priority').length ?? 0

  return (
    <div className="review-page">
      <section className="review-hero">
        <ShieldCheck />
        <div>
          <h1>作品检查</h1>
          <p>只检查你选择的章节范围内的内容，结果仅供参考，不会写入正式作品。</p>
          <button
            className="primary"
            disabled={running || !surface?.has_accepted_prose}
            title={!surface?.has_accepted_prose ? '需要先有已接受的正文才能开始检查' : undefined}
            onClick={() => void controller.start()}
          >
            <Search /> {running ? (execution?.execution_mode === 'direct' ? '后台 AI 正在执行（直接模式）…' : '检查中…') : '开始检查'}
          </button>
          {running && (
            <button onClick={() => void controller.cancel()}>
              <X /> 取消
            </button>
          )}
        </div>
      </section>
      {running && <ExecutionSummary execution={execution} />}

      <section className="panel review-surface">
        <h2>检查面（只读）</h2>
        {surfaceLoading && <p className="muted-note">正在加载…</p>}
        {surfaceError && <p className="error-text">{surfaceError}</p>}
        {!surfaceLoading && !surfaceError && surface && (
          <div className="review-stats">
            <span><strong>{surface.active_plan_count}</strong> 条有效规划</span>
            <span><strong>{surface.open_thread_count}</strong> 条未解决线索</span>
            <span><strong>{surface.chapters.length}</strong> 个已接受章节</span>
          </div>
        )}
        {surface && surface.has_accepted_prose && (
          <div className="review-chapters">
            <label>
              检查章节：
              <select
                value={selectedChapter ?? surface.latest_chapter_number ?? 1}
                onChange={(e) => controller.selectChapter(Number(e.target.value))}
              >
                {surface.chapters.map((c) => (
                  <option key={c.chapter_number} value={c.chapter_number}>第 {c.chapter_number} 章</option>
                ))}
              </select>
            </label>
          </div>
        )}
      </section>

      {error && <p className="error-text">{error}</p>}

      {report && (
        <div className="review-columns">
          <ExecutionSummary execution={execution} />
          <section className="panel review-group summary">
            <header><CheckCircle2 /><div><h2>检查结论</h2><p>第 {report.chapter_number} 章 · 结果仅供参考</p></div></header>
            <p>{report.summary}</p>
          </section>

          {(['priority', 'watch'] as const).map((sev) => {
            const issues = report.issues.filter((i) => i.severity === sev)
            const meta = severityMeta[sev]
            return (
              <section className={`panel review-group ${meta.cls}`} key={sev}>
                <header><meta.Icon /><div><h2>{meta.label} <span>{issues.length}</span></h2></div></header>
                {issues.length === 0 && <p className="muted-note">无。</p>}
                {issues.map((issue, idx) => (
                  <article key={idx}>
                    <h3>{issue.title}</h3>
                    <p>{issue.detail}</p>
                    {issue.evidence && <small>依据：{issue.evidence}</small>}
                    {issue.suggestion && <p className="suggestion">建议：{issue.suggestion}</p>}
                  </article>
                ))}
              </section>
            )
          })}

          {report.strengths.length > 0 && (
            <section className="panel review-group strength">
              <header><CheckCircle2 /><div><h2>做得好的地方</h2></div></header>
              <ul>{report.strengths.map((s, idx) => <li key={idx}>{s}</li>)}</ul>
            </section>
          )}
        </div>
      )}

      {report && priorityCount === 0 && (
        <footer className="review-note">本次检查未发现优先处理的问题；结果基于当前章节，可随内容变化重新检查。</footer>
      )}
    </div>
  )
}
