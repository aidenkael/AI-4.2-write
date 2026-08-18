import { useEffect, useState } from 'react'
import {
  getProjectOverview,
  proposeStoryPlan,
  confirmStoryPlan,
  proposeStoryWrite,
  confirmStoryWrite,
  type ProjectOverview,
  type ProposeStoryPlanResult,
  type ProposeStoryWriteResult,
} from '../bridge/client'

type OverviewState =
  | { kind: 'loading' }
  | { kind: 'ok'; overview: ProjectOverview }
  | { kind: 'error'; message: string }

type PlanningStage =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'candidate'; result: ProposeStoryPlanResult }
  | { kind: 'confirming' }
  | { kind: 'done'; message: string }
  | { kind: 'error'; message: string }

type WritingStage =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'draft'; result: ProposeStoryWriteResult }
  | { kind: 'confirming' }
  | { kind: 'done'; message: string }
  | { kind: 'error'; message: string }

export default function ProjectOverviewPage({
  projectId,
  projectName,
  warning,
  onBack,
}: {
  projectId: string
  projectName: string
  warning?: string | null
  onBack: () => void
}) {
  const [overviewState, setOverviewState] = useState<OverviewState>({ kind: 'loading' })
  const [planningStage, setPlanningStage] = useState<PlanningStage>({ kind: 'idle' })
  const [authorQuestion, setAuthorQuestion] = useState('')
  const [writingStage, setWritingStage] = useState<WritingStage>({ kind: 'idle' })
  const [authorInput, setAuthorInput] = useState('')

  const refreshOverview = () => {
    setOverviewState({ kind: 'loading' })
    getProjectOverview(projectId)
      .then((overview) => setOverviewState({ kind: 'ok', overview }))
      .catch((err) => setOverviewState({ kind: 'error', message: String(err) }))
  }

  useEffect(() => {
    refreshOverview()
  }, [projectId])

  const startPlanning = async () => {
    setPlanningStage({ kind: 'working' })
    try {
      const result = await proposeStoryPlan({
        project_id: projectId,
        author_question: authorQuestion,
      })
      setPlanningStage({ kind: 'candidate', result })
    } catch (err) {
      setPlanningStage({ kind: 'error', message: String(err) })
    }
  }

  const confirmPlanning = async (result: ProposeStoryPlanResult) => {
    setPlanningStage({ kind: 'confirming' })
    try {
      const confirmed = await confirmStoryPlan({
        project_id: result.project_id,
        planning_token: result.planning_token,
      })
      setPlanningStage({ kind: 'done', message: confirmed.message })
      setAuthorQuestion('')
      refreshOverview()
    } catch (err) {
      setPlanningStage({ kind: 'error', message: String(err) })
    }
  }

  const revisePlanning = () => {
    setPlanningStage({ kind: 'idle' })
  }

  const startWriting = async () => {
    setWritingStage({ kind: 'working' })
    try {
      const result = await proposeStoryWrite({
        project_id: projectId,
        author_input: authorInput,
      })
      setWritingStage({ kind: 'draft', result })
    } catch (err) {
      setWritingStage({ kind: 'error', message: String(err) })
    }
  }

  const confirmWriting = async (result: ProposeStoryWriteResult) => {
    setWritingStage({ kind: 'confirming' })
    try {
      const confirmed = await confirmStoryWrite({
        project_id: result.project_id,
        writing_token: result.writing_token,
      })
      setWritingStage({ kind: 'done', message: confirmed.message })
      setAuthorInput('')
      refreshOverview()
    } catch (err) {
      setWritingStage({ kind: 'error', message: String(err) })
    }
  }

  const reviseWriting = () => {
    setWritingStage({ kind: 'idle' })
  }

  return (
    <section>
      <h2>作品概览：{projectName}</h2>
      {warning && (
        <p style={{ color: '#8a6d3b', backgroundColor: '#fcf8e3', padding: '0.5rem 0.75rem', borderRadius: '4px', marginTop: '0.5rem' }}>
          {warning}
        </p>
      )}
      <button onClick={onBack} style={{ cursor: 'pointer' }}>← 返回作品列表</button>

      {overviewState.kind === 'loading' && <p>正在读取概览…</p>}
      {overviewState.kind === 'error' && <p>读取失败：{overviewState.message}</p>}

      {overviewState.kind === 'ok' && (
        <div style={{ marginTop: '1rem', lineHeight: 1.8 }}>
          {/* 已确定的故事方向 */}
          {overviewState.overview.work_direction && (
            <div>
              <h3>已确定的故事方向</h3>
              <p style={{ color: '#444' }}>{overviewState.overview.work_direction}</p>
            </div>
          )}

          {/* 读者主要期待 */}
          {overviewState.overview.reader_promise && (
            <div style={{ marginTop: '0.75rem' }}>
              <h3>读者主要期待</h3>
              <p style={{ color: '#444' }}>{overviewState.overview.reader_promise}</p>
            </div>
          )}

          {/* 当前已确定的规划 */}
          {overviewState.overview.current_plans && overviewState.overview.current_plans.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <h3>当前已确定</h3>
              <ul style={{ color: '#444', paddingLeft: '1.5rem' }}>
                {overviewState.overview.current_plans.map((plan) => (
                  <li key={plan.id} style={{ marginBottom: '0.35rem' }}>{plan.description}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 最近正文位置 */}
          {overviewState.overview.last_accepted && (
            <div style={{ marginTop: '0.75rem' }}>
              <h3>最近写作位置</h3>
              <p style={{ color: '#444' }}>{overviewState.overview.last_accepted.chapter_path}</p>
            </div>
          )}

          {/* 规划输入区 */}
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid #ddd', paddingTop: '1rem' }}>
            <h3>接下来你想一起想什么？</h3>

            {planningStage.kind === 'idle' && (
              <div>
                <textarea
                  value={authorQuestion}
                  onChange={(e) => setAuthorQuestion(e.target.value)}
                  placeholder="例如：先想想故事前半程怎么推进，我不希望男女主太早站到一起。"
                  rows={4}
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                />
                <button
                  onClick={startPlanning}
                  disabled={!authorQuestion.trim()}
                  style={{ cursor: 'pointer', padding: '0.5rem 1rem', marginTop: '0.5rem' }}
                >
                  和 AI 一起往前想
                </button>
              </div>
            )}

            {planningStage.kind === 'working' && (
              <p>正在一起想…</p>
            )}

            {planningStage.kind === 'confirming' && (
              <p>正在确认规划…</p>
            )}

            {planningStage.kind === 'done' && (
              <p style={{ color: '#2a7' }}>✓ {planningStage.message}</p>
            )}

            {planningStage.kind === 'candidate' && (
              <div style={{ lineHeight: 1.8 }}>
                <h4>可以这样往前走</h4>
                <p style={{ color: '#444' }}>{planningStage.result.candidate.proposal}</p>

                {planningStage.result.candidate.planning_items.length > 0 && (
                  <ul style={{ color: '#444', paddingLeft: '1.5rem' }}>
                    {planningStage.result.candidate.planning_items.map((item, i) => (
                      <li key={i} style={{ marginBottom: '0.35rem' }}>{item}</li>
                    ))}
                  </ul>
                )}

                <p style={{ color: '#888', fontSize: '0.85rem' }}>{planningStage.result.message}</p>

                <div style={{ marginTop: '1rem' }}>
                  <button
                    onClick={() => confirmPlanning(planningStage.result)}
                    style={{ cursor: 'pointer', padding: '0.5rem 1rem', marginRight: '0.75rem' }}
                  >
                    就这样继续
                  </button>
                  <button
                    onClick={revisePlanning}
                    style={{ cursor: 'pointer', padding: '0.5rem 1rem' }}
                  >
                    我想改一改
                  </button>
                </div>
              </div>
            )}

            {planningStage.kind === 'error' && (
              <div>
                <p style={{ color: '#b00' }}>{planningStage.message}</p>
                <button
                  onClick={() => setPlanningStage({ kind: 'idle' })}
                  style={{ cursor: 'pointer', padding: '0.5rem 1rem' }}
                >
                  返回修改
                </button>
              </div>
            )}
          </div>

          {/* 正文写作区 */}
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid #ddd', paddingTop: '1rem' }}>
            <h3>这一段你想写什么？</h3>

            {writingStage.kind === 'idle' && (
              <div>
                <textarea
                  value={authorInput}
                  onChange={(e) => setAuthorInput(e.target.value)}
                  placeholder="例如：写开场。主角第一次进入那座暴雨夜才开放的花园，但先不要解释花园的规则。"
                  rows={4}
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                />
                <button
                  onClick={startWriting}
                  disabled={!authorInput.trim()}
                  style={{ cursor: 'pointer', padding: '0.5rem 1rem', marginTop: '0.5rem' }}
                >
                  开始写
                </button>
              </div>
            )}

            {writingStage.kind === 'working' && (
              <p>正在写…</p>
            )}

            {writingStage.kind === 'confirming' && (
              <p>正在保留这段正文…</p>
            )}

            {writingStage.kind === 'done' && (
              <p style={{ color: '#2a7' }}>✓ {writingStage.message}</p>
            )}

            {writingStage.kind === 'draft' && (
              <div style={{ lineHeight: 1.8 }}>
                <h4>这一段可以这样写</h4>
                <div
                  style={{
                    color: '#333',
                    padding: '1rem',
                    backgroundColor: '#fafafa',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    whiteSpace: 'pre-wrap',
                    maxHeight: '24rem',
                    overflow: 'auto',
                  }}
                >
                  {writingStage.result.draft_text}
                </div>

                <p style={{ color: '#888', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                  {writingStage.result.message}
                </p>

                <div style={{ marginTop: '1rem' }}>
                  <button
                    onClick={() => confirmWriting(writingStage.result)}
                    style={{ cursor: 'pointer', padding: '0.5rem 1rem', marginRight: '0.75rem' }}
                  >
                    保留这段
                  </button>
                  <button
                    onClick={reviseWriting}
                    style={{ cursor: 'pointer', padding: '0.5rem 1rem' }}
                  >
                    我想改一改
                  </button>
                </div>
              </div>
            )}

            {writingStage.kind === 'error' && (
              <div>
                <p style={{ color: '#b00' }}>{writingStage.message}</p>
                <button
                  onClick={() => setWritingStage({ kind: 'idle' })}
                  style={{ cursor: 'pointer', padding: '0.5rem 1rem' }}
                >
                  返回修改
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
