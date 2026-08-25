import { ArrowRight, FolderOpen, Lightbulb, PenLine } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useIdeasController } from '../features/ideas/useIdeasController'

/**
 * 首页：真实工作台仪表盘。
 *
 * - 只展示后端真实项目列表（FormalProjectShell）；
 * - 打开 / 继续写作都先经后端校验，用正式 project_id；
 * - 快速灵感写入真实灵感箱（与灵感箱页共享同一后端存储）；
 * - 不显示任何假章节 / 字数 / 更新时间 / 最近活动 / 示例书名。
 */
export function HomePage() {
  const { actions } = useApp()
  const { projects, loading, error, openProjectById } = useFormalProjectShell()
  const ideas = useIdeasController({ notify: actions.notify })
  const [idea, setIdea] = useState('')
  const [openingId, setOpeningId] = useState<string | null>(null)

  const openAndNavigate = async (projectId: string, section: 'overview' | 'writing') => {
    setOpeningId(projectId)
    try {
      const ok = await openProjectById(projectId)
      if (ok) actions.setProjectSection(section)
    } finally {
      setOpeningId(null)
    }
  }

  const saveIdea = async () => {
    const ok = await ideas.add(idea, 'text')
    if (ok) {
      setIdea('')
      actions.notify('灵感已保存。')
    }
  }

  return (
    <div className="page home-page">
      <section className="hero">
        <div>
          <p className="eyeline"><Lightbulb /> 开始你的下一步创作</p>
          <h1>Go Write</h1>
          <p>从想法开始，到构思、规划、写作与检查，一路用真实作品数据推进。</p>
          <button className="primary" onClick={() => actions.navigate('projects')}>
            <PenLine />
            开始创作
          </button>
        </div>
      </section>

      <div className="home-grid">
        <section className="panel home-projects">
          <header>
            <h2><FolderOpen /> 我的作品</h2>
            <button className="link-button" onClick={() => actions.navigate('projects')}>
              查看全部 <ArrowRight />
            </button>
          </header>
          {loading && <p className="muted-note">正在加载正式作品…</p>}
          {!loading && error && <p className="error-text">{error}</p>}
          {!loading && !error && projects.length === 0 && (
            <p className="muted-note">还没有正式作品。去「我的作品」新建一部。</p>
          )}
          {!loading && !error && projects.length > 0 && (
            <ul>
              {projects.map((p) => (
                <li key={p.project_id}>
                  <span className="project-name">{p.name}</span>
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

        <div className="home-side">
          <section className="panel quick-idea">
            <h2><Lightbulb /> 快速记下灵感</h2>
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="此刻的想法、场景或对白…"
            />
            <button onClick={() => void saveIdea()} disabled={!idea.trim()}>
              <PenLine /> 记录
            </button>
          </section>
          <section className="panel home-entry">
            <h2>创作入口</h2>
            <button onClick={() => actions.navigate('ideas')}>灵感箱</button>
            <button onClick={() => actions.navigate('materials')}>素材与学习</button>
          </section>
        </div>
      </div>
    </div>
  )
}
