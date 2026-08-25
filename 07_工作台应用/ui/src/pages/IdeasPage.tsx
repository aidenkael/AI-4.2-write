import { Link, Lightbulb, PenLine, RefreshCw, Send, Type, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useIdeasController } from '../features/ideas/useIdeasController'
import { PageHeader } from '../components/PageHeader'
import type { IdeaKind } from '../bridge/client'

type Filter = '全部' | '尚未使用' | '已用于作品'

export function IdeasPage() {
  const { actions } = useApp()
  const { projects, openProjectById } = useFormalProjectShell()
  const controller = useIdeasController({ notify: actions.notify })
  const [value, setValue] = useState('')
  const [filter, setFilter] = useState<Filter>('全部')
  const [kind, setKind] = useState<IdeaKind>('text')
  const [developing, setDeveloping] = useState<{ id: string; content: string } | null>(null)
  const [marking, setMarking] = useState<{ id: string; content: string } | null>(null)
  const [targetProject, setTargetProject] = useState('')
  const [opening, setOpening] = useState(false)
  const [markingBusy, setMarkingBusy] = useState(false)

  const shown = useMemo(() => {
    return controller.ideas.filter((idea) => {
      if (filter === '全部') return true
      if (filter === '已用于作品') return idea.used_project_ids.length > 0
      return idea.used_project_ids.length === 0
    })
  }, [controller.ideas, filter])

  const save = async () => {
    const ok = await controller.add(value, kind)
    if (ok) setValue('')
  }

  const openDevelop = (idea: { id: string; content: string }) => {
    setDeveloping(idea)
    setTargetProject(projects[0]?.project_id ?? '')
  }

  const openMark = (idea: { id: string; content: string }) => {
    setMarking(idea)
    setTargetProject(projects[0]?.project_id ?? '')
  }

  const confirmDevelop = async () => {
    if (!developing || !targetProject) return
    setOpening(true)
    try {
      const ok = await openProjectById(targetProject)
      if (ok) {
        actions.setDevelopmentPrefill({ project_id: targetProject, text: developing.content })
        actions.setProjectSection('development')
        setDeveloping(null)
      } else {
        actions.notify('无法打开所选作品。')
      }
    } finally {
      setOpening(false)
    }
  }

  const confirmMark = async () => {
    if (!marking || !targetProject) return
    setMarkingBusy(true)
    try {
      await controller.markUsed(marking.id, targetProject)
      setMarking(null)
    } finally {
      setMarkingBusy(false)
    }
  }

  return (
    <div className="page">
      <PageHeader title="灵感箱" subtitle="随时记录闪过的想法，为创作积蓄灵感能量。" />
      <section className="panel idea-composer">
        <h3><Lightbulb /> 快速记录灵感</h3>
        <textarea value={value} onChange={(e) => setValue(e.target.value)} placeholder="此刻的想法、场景或对白…" maxLength={1000} />
        <small>{value.length}/1000</small>
        <div>
          <button className={kind === 'text' ? 'active' : ''} onClick={() => setKind('text')}><Type /> 文字</button>
          <button className={kind === 'link' ? 'active' : ''} onClick={() => setKind('link')}><Link /> 链接</button>
          <button className="primary" onClick={() => void save()} disabled={!value.trim()}><PenLine /> 记录灵感</button>
        </div>
      </section>

      <div className="idea-filters">
        {(['全部', '尚未使用', '已用于作品'] as Filter[]).map((x) => (
          <button key={x} className={filter === x ? 'active' : ''} onClick={() => setFilter(x)}>{x}</button>
        ))}
        <button className="icon-button" onClick={() => void controller.reload()} title="刷新灵感箱">
          <RefreshCw size={16} />
        </button>
      </div>

      {controller.loading && <div className="empty-state">正在加载灵感…</div>}
      {controller.error && <p className="error-text">{controller.error}</p>}

      <section className="ideas-grid">
        {shown.map((idea) => (
          <article className="panel idea-card" key={idea.id}>
            <header>
              <span>{idea.kind === 'link' ? <Link /> : <Type />}{idea.kind === 'link' ? '链接' : '文字'}</span>
              <time>{new Date(idea.created_at).toLocaleString()}</time>
            </header>
            <p>{idea.content}</p>
            <footer>
              <button
                disabled={projects.length === 0}
                title={projects.length === 0 ? '还没有正式作品，先去「我的作品」新建一部' : '把这条灵感带入故事发展'}
                onClick={() => openDevelop(idea)}
              >
                <Send /> 帮我发展
              </button>
              {idea.used_project_ids.length > 0 ? (
                <span className="soft-tag">已用于作品</span>
              ) : (
                <button
                  disabled={projects.length === 0}
                  title={projects.length === 0 ? '还没有正式作品，先去「我的作品」新建一部' : '把这条灵感标记为已用于某部作品'}
                  onClick={() => openMark(idea)}
                >
                  标记已用于作品
                </button>
              )}
              <button className="danger" onClick={() => void controller.remove(idea.id)}>
                <X /> 删除
              </button>
            </footer>
          </article>
        ))}
      </section>
      {!controller.loading && !controller.error && shown.length === 0 && (
        <div className="empty-state">没有匹配的灵感。</div>
      )}

      {developing && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => setDeveloping(null)}>
          <section className="dialog panel" role="dialog" aria-modal="true" aria-label="帮我发展" onMouseDown={(e) => e.stopPropagation()}>
            <header><h2>把灵感带入故事发展</h2><button aria-label="关闭" onClick={() => setDeveloping(null)}><X /></button></header>
            <p>选择一个正式作品，把这条灵感作为故事发展的一次预填（不会自动提交）。</p>
            {projects.length === 0 ? (
              <p className="muted-note">还没有正式作品，请先在「我的作品」新建一部。</p>
            ) : (
              <label>
                目标作品：
                <select value={targetProject} onChange={(e) => setTargetProject(e.target.value)}>
                  {projects.map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
                </select>
              </label>
            )}
            <footer>
              <button onClick={() => setDeveloping(null)}>取消</button>
              <button className="primary" disabled={!targetProject || opening} onClick={() => void confirmDevelop()}>
                {opening ? '打开中…' : '进入故事发展'}
              </button>
            </footer>
          </section>
        </div>
      )}

      {marking && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => setMarking(null)}>
          <section className="dialog panel" role="dialog" aria-modal="true" aria-label="标记已用于作品" onMouseDown={(e) => e.stopPropagation()}>
            <header><h2>标记灵感已用于作品</h2><button aria-label="关闭" onClick={() => setMarking(null)}><X /></button></header>
            <p>选择一部作品，把这条灵感标记为已使用（仅本地笔记，不写入作品状态）。</p>
            {projects.length === 0 ? (
              <p className="muted-note">还没有正式作品，请先在「我的作品」新建一部。</p>
            ) : (
              <label>
                目标作品：
                <select value={targetProject} onChange={(e) => setTargetProject(e.target.value)}>
                  {projects.map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
                </select>
              </label>
            )}
            <footer>
              <button onClick={() => setMarking(null)}>取消</button>
              <button className="primary" disabled={!targetProject || markingBusy} onClick={() => void confirmMark()}>
                {markingBusy ? '标记中…' : '标记'}
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  )
}
