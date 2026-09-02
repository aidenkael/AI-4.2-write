import { Check, Clock3, FolderOpen, Send, Sparkles, WandSparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useDevelopmentController } from '../features/development/useDevelopmentController'
import { useProjectDataController } from '../features/projectData/useProjectDataController'
import { PlanningStructure } from '../features/planning/PlanningStructure'
import {
  deferCandidatePayload,
  impactRowText,
  restoreCandidatePayload,
  unresolvedImpactCandidates,
  type StageTitleSource,
} from '../features/planning/planningImpact'
import {
  defaultNearTermRange,
  planningActionPayload,
  stageOptionsFromLengthPlan,
  validateNearTermRange,
  type PlanningMode,
} from '../features/planning/planningModes'
import { setPlanningImpactCandidateStatus } from '../bridge/client'

/**
 * 大纲与规划：真实 StoryPlan 消费者（唯一自然语言规划入口）。
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
  const impactViews = unresolvedImpactCandidates(projectData.data?.planning_impact_candidates)
  const impactStages = (
    (projectData.data?.length_plan as { stages?: Array<Record<string, unknown>> } | undefined)?.stages ?? []
  ).map((stage) => ({
    ref: typeof stage.ref === 'string' ? stage.ref : null,
    title: typeof stage.title === 'string' ? stage.title : null,
  })) as StageTitleSource[]

  const deferCandidate = async (candidateId: string) => {
    if (!selected) return
    try {
      await setPlanningImpactCandidateStatus(deferCandidatePayload(selected.project_id, candidateId))
      await projectData.reload()
    } catch (e) {
      actions.notify(e instanceof Error ? e.message : String(e))
    }
  }

  const restoreCandidate = async (candidateId: string) => {
    if (!selected) return
    try {
      await setPlanningImpactCandidateStatus(restoreCandidatePayload(selected.project_id, candidateId))
      await projectData.reload()
    } catch (e) {
      actions.notify(e instanceof Error ? e.message : String(e))
    }
  }

  const replanImpact = (candidateId: string) => {
    if (!selected || hasActiveTask) return
    setAiOpen(true)
    void c.generate({ planningMode: 'impact_replan', impactCandidateIds: [candidateId] })
  }

  // 分层规划入口：同一 StoryPlan 操作的结构化范围（全书 / 卷阶段 / 近期细化 / 自由）。
  const stageOptions = stageOptionsFromLengthPlan(
    (projectData.data?.length_plan as { stages?: Array<Record<string, unknown>> } | undefined)?.stages,
  )
  const currentChapter = Math.max(
    1,
    ...(projectData.data?.chapters ?? []).map((chapter) => chapter.chapter_number),
  )
  const [selectedStageRef, setSelectedStageRef] = useState('')
  const [nearRange, setNearRange] = useState<[number, number]>(() => defaultNearTermRange(1))
  const nearRangeInitializedRef = useRef(false)
  useEffect(() => {
    if (nearRangeInitializedRef.current || !projectData.data) return
    nearRangeInitializedRef.current = true
    setNearRange(defaultNearTermRange(currentChapter))
  }, [projectData.data, currentChapter])
  const nearError = validateNearTermRange(nearRange[0], nearRange[1])

  const startStructured = (mode: PlanningMode) => {
    if (!selected || hasActiveTask) return
    const { payload, error } = planningActionPayload(selected.project_id, {
      mode,
      stageRef: selectedStageRef || undefined,
      chapterRange: nearRange,
    })
    if (error || !payload) {
      actions.notify(error || '规划范围非法。')
      return
    }
    setAiOpen(true)
    void c.generate({
      planningMode: mode,
      stageRef: payload.stage_ref,
      chapterRange: payload.chapter_range,
    })
  }
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
      {impactViews.length > 0 && (
        <section className="panel planning-impact">
          <h3>受影响的后续规划</h3>
          <p className="muted-note">
            这些只是“可能受影响”的提示：是否重新规划由你决定；「暂时保留」不改写任何规划。
          </p>
          <ul className="planning-impact-list">
            {impactViews.map((view) => (
              <li key={view.candidateId}>
                <p>{impactRowText(view, impactStages)}</p>
                {view.status === 'deferred' && <p className="muted-note">已暂缓，可随时恢复或发起重规划。</p>}
                <div className="planning-entry-actions">
                  <button className="primary" disabled={hasActiveTask} onClick={() => replanImpact(view.candidateId)}>
                    <Sparkles /> 重新规划受影响内容
                  </button>
                  {view.status === 'deferred' ? (
                    <button onClick={() => void restoreCandidate(view.candidateId)}><Clock3 /> 恢复待处理</button>
                  ) : (
                    <button onClick={() => void deferCandidate(view.candidateId)}><Clock3 /> 暂时保留</button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="panel planning-summary planning-ai-entry">
        <p className="muted-note">选择一个规划范围；候选未经你确认不会写入正式作品。</p>
        <div className="planning-entry-actions">
          <button disabled={hasActiveTask} onClick={() => startStructured('book')}><Sparkles /> 规划全书</button>
          <label>
            卷/阶段
            <select value={selectedStageRef} onChange={(event) => setSelectedStageRef(event.target.value)}>
              <option value="">{stageOptions.length ? '选择卷/阶段' : '尚未建立卷/阶段'}</option>
              {stageOptions.map((option) => <option key={option.ref} value={option.ref}>{option.title}</option>)}
            </select>
          </label>
          <button disabled={hasActiveTask || !selectedStageRef} onClick={() => startStructured('stage')}><Sparkles /> 规划本卷 / 阶段</button>
          <label>
            近期章节
            <input
              type="number" min={1} value={nearRange[0]}
              onChange={(event) => setNearRange([Number(event.target.value), nearRange[1]])}
            />
            –
            <input
              type="number" min={1} value={nearRange[1]}
              onChange={(event) => setNearRange([nearRange[0], Number(event.target.value)])}
            />
          </label>
          <button disabled={hasActiveTask || !!nearError} onClick={() => startStructured('near_term')}><Sparkles /> 细化近期章节</button>
          <button onClick={() => setAiOpen(true)}><WandSparkles /> 自由规划</button>
        </div>
        {nearError && <p className="error-text">{nearError}</p>}
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
