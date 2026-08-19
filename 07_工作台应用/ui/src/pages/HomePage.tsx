import { useEffect } from 'react'
import {
  cancelNewProjectRequest,
  confirmNewProject,
  getNewProjectRequest,
  prepareNewProject,
  type ConfirmResult,
  type ProposeResult,
} from '../bridge/client'

export type HomeStage =
  | { kind: 'input' }
  | { kind: 'preparing' }
  | { kind: 'waiting'; requestId: string }
  | { kind: 'candidate'; result: ProposeResult }
  | { kind: 'confirming' }
  | { kind: 'error'; message: string }

const POLL_INTERVAL_MS = 3000

export default function HomePage({
  name,
  setName,
  idea,
  setIdea,
  stage,
  setStage,
  onProjectCreated,
}: {
  name: string
  setName: (v: string) => void
  idea: string
  setIdea: (v: string) => void
  stage: HomeStage
  setStage: (s: HomeStage) => void
  onProjectCreated: (p: { project_id: string; name: string; warning?: string | null }) => void
}) {
  const startPrepare = async () => {
    setStage({ kind: 'preparing' })
    try {
      const prepared = await prepareNewProject({ name, idea })
      setStage({ kind: 'waiting', requestId: prepared.request_id })
    } catch (err) {
      setStage({ kind: 'error', message: String(err) })
    }
  }

  // 等待阶段：轮询 Qoder 写回结果（Go Write 不运行模型，模型由 Qoder /gowrite 执行）
  useEffect(() => {
    if (stage.kind !== 'waiting') return
    let cancelled = false

    const tick = async () => {
      try {
        const status = await getNewProjectRequest(stage.requestId)
        if (cancelled) return
        if (status.status === 'completed' && status.result) {
          setStage({ kind: 'candidate', result: status.result })
        } else if (status.status === 'failed') {
          setStage({ kind: 'error', message: status.error || '任务失败，请重新发起。' })
        } else if (status.status === 'expired') {
          setStage({ kind: 'error', message: status.error || '任务已超时，请重新发起。' })
        } else if (status.status === 'canceled') {
          setStage({ kind: 'input' })
        }
        // pending → 继续等
      } catch (err) {
        if (cancelled) return
        setStage({ kind: 'error', message: String(err) })
      }
    }

    void tick() // 立即查一次，快速响应已写回的结果
    const id = window.setInterval(() => void tick(), POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [stage, setStage])

  const cancelWait = async () => {
    if (stage.kind !== 'waiting') return
    try {
      await cancelNewProjectRequest(stage.requestId)
    } catch {
      // 取消失败也回到输入态（后台终会清理）
    }
    setStage({ kind: 'input' })
  }

  const confirm = async (result: ProposeResult) => {
    setStage({ kind: 'confirming' })
    try {
      const created: ConfirmResult = await confirmNewProject({
        proposal_token: result.proposal_token,
      })
      onProjectCreated({
        project_id: created.project_id,
        name: created.name,
        warning: created.warning,
      })
    } catch (err) {
      setStage({ kind: 'error', message: String(err) })
    }
  }

  const revise = () => {
    // "我想改一改"：回到输入（作品名与想法保留在 state），作者修改后重新生成候选
    setStage({ kind: 'input' })
  }

  return (
    <section style={{ maxWidth: '46rem' }}>
      <h2>新建作品</h2>

      {stage.kind === 'input' && (
        <div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem' }}>作品名：</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：暴雨夜的花园"
              style={{ width: '24rem', padding: '0.35rem' }}
            />
          </div>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={{ display: 'block', marginBottom: '0.25rem' }}>我的想法：</label>
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="用自然语言写下你的想法……"
              rows={5}
              style={{ width: '100%', padding: '0.35rem', boxSizing: 'border-box' }}
            />
          </div>
          <button
            onClick={startPrepare}
            disabled={!name.trim() || !idea.trim()}
            style={{ cursor: 'pointer', padding: '0.45rem 1rem' }}
          >
            和 AI 一起想想
          </button>
        </div>
      )}

      {stage.kind === 'preparing' && (
        <p style={{ marginTop: '1.5rem' }}>正在准备任务……</p>
      )}

      {stage.kind === 'waiting' && (
        <div style={{ marginTop: '1.5rem', lineHeight: 1.8 }}>
          <p>任务已准备好，请到 Qoder 输入 /gowrite 并回车。</p>
          <p style={{ color: '#888', fontSize: '0.85rem' }}>
            Go Write 不直接运行模型；请在 Qoder 桌面端执行 /gowrite，结果会自动回到这里。
          </p>
          <button
            onClick={cancelWait}
            style={{ cursor: 'pointer', padding: '0.45rem 1rem', marginTop: '0.5rem' }}
          >
            取消任务
          </button>
        </div>
      )}

      {stage.kind === 'confirming' && (
        <p style={{ marginTop: '1.5rem' }}>正在创建作品……</p>
      )}

      {stage.kind === 'candidate' && (
        <div style={{ marginTop: '1rem', lineHeight: 1.8 }}>
          <h3>我理解的方向</h3>
          <p style={{ color: '#444' }}>
            {stage.result.candidate.work_direction || stage.result.candidate.proposal}
          </p>

          {stage.result.candidate.proposal && (
            <p style={{ color: '#444' }}>故事大致会是：{stage.result.candidate.proposal}</p>
          )}
          {stage.result.candidate.reader_promise && (
            <p style={{ color: '#444' }}>读者最主要会期待：{stage.result.candidate.reader_promise}</p>
          )}
          {stage.result.candidate.hard_constraints.length > 0 && (
            <p style={{ color: '#444' }}>
              目前最好先守住：
              {stage.result.candidate.hard_constraints.join('；')}
            </p>
          )}
          {stage.result.candidate.open_space.length > 0 && (
            <p style={{ color: '#444' }}>
              还可以自由变化的部分：
              {stage.result.candidate.open_space.join('；')}
            </p>
          )}

          <p style={{ color: '#888', fontSize: '0.85rem' }}>{stage.result.message}</p>

          <div style={{ marginTop: '1rem' }}>
            <button
              onClick={() => confirm(stage.result)}
              style={{ cursor: 'pointer', padding: '0.45rem 1rem', marginRight: '0.75rem' }}
            >
              就按这个方向
            </button>
            <button
              onClick={() => revise()}
              style={{ cursor: 'pointer', padding: '0.45rem 1rem' }}
            >
              我想改一改
            </button>
          </div>
        </div>
      )}

      {stage.kind === 'error' && (
        <div style={{ marginTop: '1rem' }}>
          <p style={{ color: '#b00' }}>{stage.message}</p>
          <button
            onClick={() => setStage({ kind: 'input' })}
            style={{ cursor: 'pointer', padding: '0.45rem 1rem' }}
          >
            返回修改
          </button>
        </div>
      )}
    </section>
  )
}
