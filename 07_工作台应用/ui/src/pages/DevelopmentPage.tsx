import { Check, Clock3, FolderOpen, PenLine, RefreshCw, Send, Sparkles, ThumbsUp, WandSparkles, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { useApp, useIllustration } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useDevelopmentController } from '../features/development/useDevelopmentController'

/**
 * 故事发展：真实 StoryPlan 消费者。
 *
 * - 正式身份来自 FormalProjectShell（唯一 project_id），不使用 Mock 身份；
 * - 正式事实只来自 getProjectOverview（current_plans / work_direction / reader_promise）；
 * - 候选是后端返回的单个非 canonical 规划候选（proposal + planning_items），只读；
 * - 确认只通过 confirmStoryPlan 写 approved_plan；展示在确认后从正式概览重载；
 * - 执行模式由 Settings 决定（Direct 后台执行 / Interactive /gowrite），UI 不分支；
 * - 支持一次性灵感预填（"帮我发展"）：项目匹配时填入问题，绝不自动提交。
 */
export function DevelopmentPage() {
  const { actions } = useApp()
  const city = useIllustration('city')
  const { selected } = useFormalProjectShell()
  const c = useDevelopmentController({ projectId: selected?.project_id ?? null, notify: actions.notify })
  const { state } = c
  const questionInputRef = useRef<HTMLInputElement>(null)
  const hasActiveTask = state.status === 'running' || state.status === 'confirming'
  const canGenerate = !!selected && state.authorQuestion.trim().length > 0 && !state.requestId

  // 一次性灵感预填：项目匹配时填入问题并立即清除（session-only，绝不自动提交）
  const consumedPrefillRef = useRef(false)
  useEffect(() => {
    if (consumedPrefillRef.current) return
    if (!selected) return
    const prefill = actions.consumeDevelopmentPrefill()
    if (prefill && prefill.project_id === selected.project_id && prefill.text) {
      consumedPrefillRef.current = true
      c.setAuthorQuestion(prefill.text)
    }
  }, [selected, actions, c])

  // 未选择正式作品：安全空态 + 返回作品列表；不调用 StoryPlan 后端
  if (!selected) {
    return (
      <div className="development-page">
        <section className="panel decision">
          <h2>
            <Sparkles />
            故事发展
          </h2>
          <div className="empty-state">
            <p>请先在「我的作品」中选择一部正式作品。</p>
            <button className="primary" onClick={() => actions.navigate('projects')}>
              <FolderOpen />
              返回作品列表
            </button>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="development-page">
      <section className="decision panel" style={{ backgroundImage: `linear-gradient(90deg,#fff 30%,rgba(255,255,255,.6)),url(${city})`, backgroundSize: 'cover', backgroundPosition: 'center' }}>
        <h2>
          <Sparkles />
          现在最值得决定什么
        </h2>
        <p>写下你想一起想的问题，AI 会基于已确认的规划给出一个建议方向。</p>
        <label>
          当前故事问题：
          <input
            ref={questionInputRef}
            value={state.authorQuestion}
            onChange={(e) => c.setAuthorQuestion(e.target.value)}
            placeholder="例如：主角是否应该向盟友揭露真相，还是继续隐瞒？"
          />
        </label>

        {state.status === 'loading' && (
          <div className="running">
            <span />
            正在加载正式规划数据…
          </div>
        )}

        {state.status === 'running' && (
          <>
            <div className="running">
              <span />
              <strong>{state.execution?.execution_mode === 'direct' ? '后台 AI 正在执行（直接模式）…' : '等待交互桥 /gowrite…'}</strong>
            </div>
            {state.backendMessage && <p className="muted-note">{state.backendMessage}</p>}
            <div className="candidate-actions">
              <button onClick={() => void c.cancel()}>
                <X />
                取消
              </button>
            </div>
          </>
        )}

        {state.status === 'confirming' && (
          <>
            {state.candidate && (
              <div className="candidate-view">
                <strong>建议方向（待确认）</strong>
                <p>{state.candidate.proposal}</p>
                <ul>
                  {state.candidate.planning_items.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="confirming-note">正在采用…</div>
          </>
        )}

        {state.status === 'waiting_confirmation' && state.candidate && (
          <>
            <ExecutionSummary execution={state.execution} />
            <div className="candidate-view">
              <strong>建议方向（待确认）</strong>
              <p>{state.candidate.proposal}</p>
              <ul>
                {state.candidate.planning_items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="candidate-actions">
              <button className="primary" onClick={() => void c.confirm()}>
                <Check />
                采用这个方向
              </button>
              <button onClick={() => void c.regenerate()}>
                <WandSparkles />
                换一个建议
              </button>
              <button onClick={() => void c.discard()}>
                <Clock3 />
                暂时不决定
              </button>
            </div>
          </>
        )}

        {state.status === 'accepted' && (
          <span className="accepted-note">
            <Check />
            已采用，规划已写入正式作品。
          </span>
        )}

        <div className="decision-actions">
          <button
            className="primary"
            onClick={() => void c.generate()}
            disabled={!canGenerate || hasActiveTask}
          >
            <ThumbsUp />
            {state.status === 'running' ? '思考中…' : '你推荐'}
          </button>
          <button
            onClick={() => void c.regenerate()}
            disabled={!state.candidate || hasActiveTask}
            title={state.candidate ? '先丢弃当前建议，再以同一问题重新生成' : '需要先有一个建议'}
          >
            <WandSparkles />
            换一个建议
          </button>
          <button
            onClick={() => {
              c.setAuthorQuestion('')
              questionInputRef.current?.focus()
            }}
            disabled={hasActiveTask}
          >
            <PenLine />
            我自己说
          </button>
          <button
            onClick={() => void c.discard()}
            disabled={!state.requestId && !state.candidate}
          >
            <Clock3 />
            暂时不决定
          </button>
        </div>

        {state.error && <p className="error-text">{state.error}</p>}
      </section>

      <div className="development-summary">
        <section className="panel confirmed">
          <h3>● 当前已确认规划</h3>
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
            state.overview.current_plans.map((plan) => <p key={plan.id}>• {plan.description}</p>)
          ) : (
            <p className="muted-note">还没有已确认规划。</p>
          )}
        </section>
        <section className="panel future">
          <h3>✦ 作品方向</h3>
          {state.overview?.work_direction ? (
            <p>{state.overview.work_direction}</p>
          ) : (
            <p className="muted-note">暂未记录。</p>
          )}
        </section>
        <section className="panel unresolved">
          <h3>？ 读者期待</h3>
          {state.overview?.reader_promise ? (
            <p>{state.overview.reader_promise}</p>
          ) : (
            <p className="muted-note">暂未记录。</p>
          )}
        </section>
      </div>

      <form
        className="chatbar"
        onSubmit={(e) => {
          e.preventDefault()
          void c.generate()
        }}
      >
        <Sparkles />
        <input
          value={state.authorQuestion}
          onChange={(e) => c.setAuthorQuestion(e.target.value)}
          placeholder="和 AI 说说你的想法，或输入新的故事问题…"
        />
        <button disabled={!canGenerate || hasActiveTask}>
          <Send />
          发送
        </button>
      </form>
    </div>
  )
}
