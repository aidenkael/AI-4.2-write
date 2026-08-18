import { useState } from 'react'
import {
  confirmNewProject,
  proposeNewProject,
  type ConfirmResult,
  type ProposeResult,
} from '../bridge/client'

type Stage =
  | { kind: 'input' }
  | { kind: 'working' }
  | { kind: 'candidate'; result: ProposeResult }
  | { kind: 'confirming' }
  | { kind: 'error'; message: string }

export default function HomePage({
  onProjectCreated,
}: {
  onProjectCreated: (p: { project_id: string; name: string }) => void
}) {
  const [name, setName] = useState('')
  const [idea, setIdea] = useState('')
  const [stage, setStage] = useState<Stage>({ kind: 'input' })

  const startPropose = async () => {
    setStage({ kind: 'working' })
    try {
      const result = await proposeNewProject({ name, idea })
      setStage({ kind: 'candidate', result })
    } catch (err) {
      setStage({ kind: 'error', message: String(err) })
    }
  }

  const confirm = async (result: ProposeResult) => {
    setStage({ kind: 'confirming' })
    try {
      const created: ConfirmResult = await confirmNewProject({
        proposal_token: result.proposal_token,
      })
      onProjectCreated({ project_id: created.project_id, name: created.name })
    } catch (err) {
      setStage({ kind: 'error', message: String(err) })
    }
  }

  const revise = () => {
    // “我想改一改”：回到输入（作品名与想法保留在 state），作者修改后重新生成候选
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
            onClick={startPropose}
            disabled={!name.trim() || !idea.trim()}
            style={{ cursor: 'pointer', padding: '0.45rem 1rem' }}
          >
            和 AI 一起想想
          </button>
        </div>
      )}

      {stage.kind === 'working' && (
        <p style={{ marginTop: '1.5rem' }}>正在整理你的想法……</p>
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
