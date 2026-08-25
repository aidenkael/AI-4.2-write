import { Check, FolderOpen, PenLine, Plus, RefreshCw, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { PageHeader } from '../components/PageHeader'
import { defaultIllustrations } from '../assets/illustrations'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useNewProjectController } from '../features/projects/useNewProjectController'

/**
 * 我的作品：真实正式项目列表 + 真实新建作品生命周期。
 *
 * - 每个项目只显示真实项目名；打开/继续写作先经后端校验；
 * - 新建作品：作品名 + 一句话想法 → Generate → 后端候选 → 确认 → 创建正式项目。
 */
export function ProjectsPage() {
  const { actions } = useApp()
  const { projects, loading, error, reload, openProjectById } = useFormalProjectShell()
  const [openingId, setOpeningId] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const np = useNewProjectController({ notify: actions.notify })

  const openAndNavigate = async (projectId: string, section: 'overview' | 'writing') => {
    setOpeningId(projectId)
    try {
      const ok = await openProjectById(projectId)
      if (ok) actions.setProjectSection(section)
    } finally {
      setOpeningId(null)
    }
  }

  const confirmNew = async () => {
    // 用 confirm() 的返回值驱动后续流程：绝不在 await setState 之后读
    // 旧闭包里的 np.state.confirmed（那是本次渲染前的值，必然为 null，
    // 会导致“作品已创建，正在打开…”永远卡住）。
    const confirmed = await np.confirm()
    if (!confirmed) return
    setShowNew(false)
    await reload()
    const ok = await openProjectById(confirmed.project_id)
    if (ok) actions.setProjectSection('overview')
    np.reset()
  }

  return (
    <div className="page">
      <PageHeader
        title="我的作品"
        subtitle="从正式作品工程中选择并继续创作"
        art={defaultIllustrations.mountains}
        action={
          <button className="primary" onClick={() => setShowNew(true)}>
            <Plus /> 新建作品
          </button>
        }
      />
      {loading && <div className="empty-state">正在加载正式作品…</div>}
      {!loading && error && (
        <div className="empty-state">
          <p className="error-text">{error}</p>
          <button onClick={() => void reload()}><RefreshCw /> 重试</button>
        </div>
      )}
      {!loading && !error && projects.length === 0 && (
        <div className="empty-state">
          <p>暂无正式作品。</p>
          <p className="muted-note">点击「新建作品」，从一个想法开始。</p>
        </div>
      )}
      {!loading && !error && projects.length > 0 && (
        <div className="projects-featured">
          {(() => {
            const first = projects[0]
            return (
              <section className="featured-project panel">
                <div className="featured-art formal-art" />
                <div>
                  <div className="title-row">
                    <h2>{first.name}</h2>
                    <span className="soft-tag">正式作品</span>
                  </div>
                  <p className="muted-note">从正式作品工程中选择并继续创作。</p>
                  <div>
                    <button className="primary" disabled={openingId === first.project_id} onClick={() => void openAndNavigate(first.project_id, 'writing')}>
                      <PenLine /> 继续写作
                    </button>
                    <button disabled={openingId === first.project_id} onClick={() => void openAndNavigate(first.project_id, 'overview')}>
                      <FolderOpen /> 打开作品
                    </button>
                  </div>
                </div>
              </section>
            )
          })()}
          <div className="project-cards">
            {projects.slice(1).map((p) => (
              <article className="project-card panel" key={p.project_id}>
                <div className="project-thumb formal-art" />
                <div>
                  <div className="title-row">
                    <h3>{p.name}</h3>
                    <span className="soft-tag">正式作品</span>
                  </div>
                  <div>
                    <button className="primary" disabled={openingId === p.project_id} onClick={() => void openAndNavigate(p.project_id, 'writing')}>
                      <PenLine /> 继续写作
                    </button>
                    <button disabled={openingId === p.project_id} onClick={() => void openAndNavigate(p.project_id, 'overview')}>
                      <FolderOpen /> 打开作品
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      {showNew && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => { if (np.state.status !== 'running' && np.state.status !== 'confirming') setShowNew(false) }}>
          <section className="dialog form-dialog panel new-project-dialog" role="dialog" aria-modal="true" aria-label="新建作品" onMouseDown={(e) => e.stopPropagation()}>
            <header>
              <h2><Sparkles /> 新建作品</h2>
              <button aria-label="关闭" onClick={() => setShowNew(false)}><X /></button>
            </header>

            {np.state.status !== 'accepted' && (
              <div className="form-fields">
                <label>作品名<input value={np.state.name} onChange={(e) => np.setName(e.target.value)} placeholder="给作品起个名字" disabled={np.state.status === 'running' || np.state.status === 'confirming'} /></label>
                <label>一句话想法<textarea value={np.state.idea} onChange={(e) => np.setIdea(e.target.value)} placeholder="用一句话说说你想写的故事…" disabled={np.state.status === 'running' || np.state.status === 'confirming'} /></label>

                {np.state.status === 'running' && (
                  <>
                    <div className="running"><span /> {np.state.execution?.execution_mode === 'direct' ? '后台 AI 正在执行（直接模式）…' : '等待交互桥 /gowrite…'}</div>
                    {np.state.backendMessage && <p className="muted-note">{np.state.backendMessage}</p>}
                  </>
                )}
                {np.state.status === 'running' && (
                  <button onClick={() => void np.cancel()}><X /> 取消</button>
                )}

                {np.state.status === 'confirming' && np.state.candidate && (
                  <div className="candidate-view">
                    <strong>方向候选（待确认）</strong>
                    <p>{np.state.candidate.proposal}</p>
                    <div className="confirming-note">正在创建作品…</div>
                  </div>
                )}

                {np.state.status === 'waiting_confirmation' && np.state.candidate && (
                  <>
                    <ExecutionSummary execution={np.state.execution} />
                    <div className="candidate-view">
                      <strong>方向候选（待确认）</strong>
                      <p><b>作品方向：</b>{np.state.candidate.work_direction}</p>
                      <p><b>读者期待：</b>{np.state.candidate.reader_promise}</p>
                      <p>{np.state.candidate.proposal}</p>
                      {np.state.candidate.hard_constraints.length > 0 && (
                        <p className="muted-note">建议约束：{np.state.candidate.hard_constraints.join('、')}</p>
                      )}
                      {np.state.candidate.unknowns.length > 0 && (
                        <p className="muted-note">留待决定：{np.state.candidate.unknowns.join('、')}</p>
                      )}
                    </div>
                    <div className="candidate-actions">
                      <button className="primary" onClick={() => void confirmNew()}><Check /> 确认创建</button>
                      <button onClick={() => void np.regenerate()}><RefreshCw /> 换一个</button>
                      <button onClick={() => void np.discard()}>不要了</button>
                    </div>
                  </>
                )}

                {np.state.error && <p className="error-text">{np.state.error}</p>}

                {(np.state.status === 'idle' || np.state.status === 'failed') && (
                  <button className="primary wide" disabled={!np.state.name.trim() || !np.state.idea.trim()} onClick={() => void np.generate()}>
                    <Sparkles /> 生成候选方向
                  </button>
                )}
              </div>
            )}

            {np.state.status === 'accepted' && (
              <div className="accepted-note"><Check /> 作品已创建，正在打开…</div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
