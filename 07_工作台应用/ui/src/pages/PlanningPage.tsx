import { Check, Clock3, FolderOpen, RefreshCw, Send, Sparkles, WandSparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useDevelopmentController } from '../features/development/useDevelopmentController'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { PlanningStructure } from '../features/planning/PlanningStructure'

/**
 * 故事规划：真实 StoryPlan 消费者（唯一自然语言规划入口）。
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id），不使用 Mock 身份；
 * - 正式事实只来自 getProjectOverview（current_plans / work_direction / reader_promise）；
 * - 候选是后端返回的单个非 canonical 规划候选（proposal + planning_items），只读；
 *   未经作者确认不是已批准规划；确认后从正式概览重载；
 * - 执行模式由 Settings 决定（Direct 后台执行 / Interactive /gowrite），UI 不分支；
 * - 支持一次性规划预填（灵感箱"帮我发展" / 正在写"给我几个方案"）：
 *   项目匹配时填入问题，绝不自动提交；
 * - 页面上只有一个规划输入，不再同时存在顶部输入与底部聊天条两个竞争入口。
 */
export function PlanningPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const c = useDevelopmentController({ projectId: selected?.project_id ?? null, notify: actions.notify })
  const projectData = useProjectDataController(selected?.project_id ?? null)
  const { state } = c
  const questionInputRef = useRef<HTMLTextAreaElement>(null)
  const [aiOpen, setAiOpen] = useState(false)
  const hasActiveTask = state.status === 'running' || state.status === 'confirming' || state.status === 'waiting_confirmation'
  const aiDetailVisible = aiOpen || hasActiveTask
  const canGenerate = !!selected && state.authorQuestion.trim().length > 0 && !state.requestId

  // 一次性规划预填：项目匹配时填入问题并立即清除（session-only，绝不自动提交）
  const consumedPrefillRef = useRef(false)
  useEffect(() => {
    if (consumedPrefillRef.current) return
    if (!selected) return
    const prefill = actions.consumePlanningPrefill()
    if (prefill && prefill.project_id === selected.project_id && prefill.text) {
      consumedPrefillRef.current = true
      c.setAuthorQuestion(prefill.text)
      setAiOpen(true)
    }
  }, [selected, actions, c])

  // 未选择正式作品：安全空态 + 返回作品页；不调用 StoryPlan 后端
  if (!selected) {
    return (
      <div className="planning-page">
        <section className="panel planning-main">
          <div className="empty-state">
            <p>请先在「作品」中选择一部正式作品。</p>
            <button className="primary" onClick={() => actions.navigate('works')}>
              <FolderOpen />
              返回作品
            </button>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="planning-page">
      <PlanningStructure controller={projectData} />
      <section className="panel planning-summary">
        <div>
          <h3>当前已确认规划</h3>
          {state.overviewLoading ? (
            <p className="muted-note">正在加载…</p>
          ) : state.overviewError ? (
            <>
              <p className="error-text">{state.overviewError}</p>
              <button onClick={() => void c.reloadOverview()}>
                <RefreshCw />
                重试
              </button>
            </>
          ) : state.overview?.current_plans && state.overview.current_plans.length > 0 ? (
            <ul className="planning-list">
              {state.overview.current_plans.map((plan) => <li key={plan.id}>{plan.description}</li>)
              }
            </ul>
          ) : (
            <p className="muted-note">还没有已确认规划。</p>
          )}
        </div>
        <button onClick={() => setAiOpen(true)}><Sparkles /> 让 AI 帮我规划</button>
      </section>

      {aiDetailVisible && (
        <aside className="record-drawer planning-ai-drawer panel" aria-label="AI 规划">
          <header><h2><Sparkles /> 让 AI 帮我规划</h2><button aria-label="关闭" onClick={() => setAiOpen(false)}><X /></button></header>
          <div className="record-drawer-body">
            <p className="muted-note">用自然语言写下你想一起想的问题。候选未经你确认不会写入正式作品。</p>
            <form
              className="planning-entry"
              onSubmit={(e) => {
                e.preventDefault()
                if (canGenerate && !hasActiveTask) void c.generate()
              }}
            >
              <textarea ref={questionInputRef} value={state.authorQuestion} onChange={(e) => c.setAuthorQuestion(e.target.value)} placeholder="例如：主角是否应该向盟友揭露真相，还是继续隐瞒？" rows={3} />
              <div className="planning-entry-actions">
                <button className="primary" type="submit" disabled={!canGenerate || hasActiveTask}><Send />{state.status === 'running' ? '思考中…' : '生成建议方向'}</button>
                {state.status === 'running' && <button type="button" onClick={() => void c.cancel()}><X /> 取消</button>}
              </div>
            </form>
            {state.status === 'loading' && <div className="running"><span />正在加载正式规划数据…</div>}
            {state.status === 'running' && <div className="running"><span /><strong>{state.execution?.execution_mode === 'interactive_bridge' ? '请到 Qoder 执行 /gowrite' : 'AI 正在规划'}</strong></div>}
            {state.status === 'confirming' && state.candidate && <div className="candidate-view"><strong>规划候选 · 等待你确认</strong><p>{state.candidate.proposal}</p><ul>{state.candidate.planning_items.map((item, i) => <li key={i}>{item}</li>)}</ul><div className="confirming-note">正在采用…</div></div>}
            {state.status === 'waiting_confirmation' && state.candidate && <div className="candidate-view"><strong>规划候选 · 等待你确认</strong><p>{state.candidate.proposal}</p><ul>{state.candidate.planning_items.map((item, i) => <li key={i}>{item}</li>)}</ul><div className="candidate-actions"><button className="primary" onClick={() => void c.confirm()}><Check />采用这个方向</button><button onClick={() => void c.regenerate()}><WandSparkles />换一个建议</button><button onClick={() => void c.discard()}><Clock3 />暂时不决定</button></div></div>}
            {state.status === 'accepted' && <span className="accepted-note"><Check />已采用，规划已写入正式作品。</span>}
            {state.error && <p className="error-text">{state.error}</p>}
          </div>
        </aside>
      )}
    </div>
  )
}
