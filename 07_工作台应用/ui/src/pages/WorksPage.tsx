import { Check, FolderOpen, Lightbulb, PenLine, Plus, RefreshCw, Sparkles, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { PageHeader } from '../components/PageHeader'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useNewProjectController } from '../features/projects/useNewProjectController'
import { useIdeasController } from '../features/ideas/useIdeasController'
import { useAuthorTask } from '../features/tasks/AuthorTaskCoordinator'

/**
 * 作品：唯一的作者落地页（原首页 + 我的作品合并，不再保留两套重复入口）。
 *
 * - 真实正式项目列表（FormalProjectShell）、打开 / 继续写作先经后端校验；
 * - 新建作品真实生命周期：作品名 + 一句话想法 → 生成候选 → 确认创建；
 *   任务属于 App 级协调器：离开本页任务继续、候选保留，返回自动打开对话框。
 * - 快速灵感写入真实灵感箱（与灵感箱页共享同一后端存储）；
 * - 不显示任何假章节数 / 字数 / 更新时间 / 最近活动 / 进度 / 封面。
 */
export function WorksPage() {
  const { actions } = useApp()
  const { projects, loading, error, reload, openProjectById } = useFormalProjectShell()
  const { task } = useAuthorTask()
  const ideas = useIdeasController({ notify: actions.notify })
  const np = useNewProjectController({ notify: actions.notify })
  const [openingId, setOpeningId] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [idea, setIdea] = useState('')

  // 协调器存在 new_project 任务时自动打开对话框（返回后候选仍可见）
  useEffect(() => {
    if (task?.kind === 'new_project') setShowNew(true)
  }, [task])

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
    // 用 confirm() 的返回值驱动后续流程：绝不在 await setState 之后读旧闭包里的状态
    const confirmed = await np.confirm()
    if (!confirmed) return
    setShowNew(false)
    await reload()
    const ok = await openProjectById(confirmed.project_id)
    if (ok) actions.setProjectSection('overview')
    np.reset()
  }

  const saveIdea = async () => {
    const ok = await ideas.add(idea, 'text')
    if (ok) {
      setIdea('')
      actions.notify('灵感已保存。')
    }
  }

  return (
    <div className="page works-page">
      <PageHeader
        title="作品"
        subtitle="选择一部正式作品继续创作，或从一个想法开始新建"
        action={
          <button className="primary" onClick={() => setShowNew(true)}>
            <Plus /> 新建作品
          </button>
        }
      />

      <div className="works-grid">
        <section className="panel works-projects">
          <header>
            <h2><FolderOpen /> 正式作品</h2>
          </header>
          {loading && <p className="muted-note">正在加载正式作品…</p>}
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
            <ul>
              {projects.map((p) => (
                <li key={p.project_id}>
                  <span className="project-name">{p.name}</span>
                  <span className="soft-tag">正式作品</span>
                  <button
                    className="primary"
                    disabled={openingId === p.project_id}
                    onClick={() => void openAndNavigate(p.project_id, 'writing')}
                  >
                    <PenLine /> 继续写作
                  </button>
                  <button
                    disabled={openingId === p.project_id}
                    onClick={() => void openAndNavigate(p.project_id, 'overview')}
                  >
                    打开作品
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel works-idea">
          <h2><Lightbulb /> 快速记下灵感</h2>
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="此刻的想法、场景或对白…"
          />
          <footer>
            <button className="link-button" onClick={() => actions.navigate('ideas')}>打开灵感箱</button>
            <button onClick={() => void saveIdea()} disabled={!idea.trim()}>
              <PenLine /> 记录
            </button>
          </footer>
        </section>
      </div>

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
