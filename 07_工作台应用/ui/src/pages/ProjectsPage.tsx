import { Clock3, FolderOpen, MoreHorizontal, PenLine, Plus } from 'lucide-react'
import { useState } from 'react'
import { MockFormDialog } from '../components/MockFormDialog'
import { PageHeader } from '../components/PageHeader'
import { useApp, useIllustration } from '../features/app/AppStore'

export function ProjectsPage() {
  const { state, actions } = useApp(); const [creating, setCreating] = useState(false); const [title, setTitle] = useState(''); const [subtitle, setSubtitle] = useState('')
  const mountains = useIllustration('mountains'); const city = useIllustration('city'); const desk = useIllustration('desk'); const art = { city, desk, mountains }
  const featured = state.projects[0]; const rest = state.projects.slice(1)
  const submit = (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!title.trim()) return; actions.createProject(title.trim(), subtitle.trim() || '一部刚刚开始构思的新作品。'); setCreating(false); setTitle(''); setSubtitle('') }
  return <div className="page"><PageHeader title="我的作品" subtitle="继续创作，管理你的写作项目" art={mountains} action={<button className="primary" onClick={() => setCreating(true)}><Plus/>新建作品</button>}/>
    <section className="featured-project panel"><div className="featured-art" style={{ backgroundImage: `url(${art[featured.art]})` }}/><div><div className="title-row"><h2>{featured.title}</h2><span className="soft-tag">{featured.status}</span></div><p>{featured.subtitle}</p><div className="project-stats"><span>📖 当前章节<strong>第 {featured.chapter} 章</strong></span><span>✎ 当前字数<strong>{featured.words.toLocaleString()} 字</strong></span><span>◷ 最近更新<strong>{featured.updated}</strong></span></div><button className="primary" onClick={() => actions.openProject(featured.id,'writing')}><PenLine/>继续写作</button><button onClick={() => actions.openProject(featured.id,'overview')}><FolderOpen/>打开作品</button></div></section>
    <div className="project-cards">{rest.map((project) => <article className="project-card panel" key={project.id}><div className="project-thumb" style={{ backgroundImage: `url(${art[project.art]})` }}/><div><div className="title-row"><h3>{project.title}</h3><span className="soft-tag">{project.status}</span></div><p>{project.subtitle}</p><small><Clock3/>最近更新：{project.updated}</small><small>📖 当前字数：{project.words.toLocaleString()} 字</small><div><button onClick={() => actions.openProject(project.id,'writing')}>继续写作</button><button onClick={() => actions.openProject(project.id,'overview')}><FolderOpen/>打开作品</button><button aria-label={`${project.title} 更多操作`} onClick={() => actions.openDialog(`${project.title} 的更多操作`, 'Mock 操作包括重命名、归档和查看项目摘要；不会修改正式作品数据。')}><MoreHorizontal/></button></div></div></article>)}</div>
    {creating && <MockFormDialog title="新建作品" submitLabel="创建并打开" onClose={() => setCreating(false)} onSubmit={submit}><label>作品名称<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：雾港来信" required/></label><label>一句话简介<textarea value={subtitle} onChange={(event) => setSubtitle(event.target.value)} placeholder="这部作品从哪里开始？"/></label></MockFormDialog>}
  </div>
}
