import { Clock3, FolderOpen, MoreHorizontal, PenLine, Plus } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { projects } from '../mock/data'
import { useApp, useIllustration } from '../features/app/AppStore'

export function ProjectsPage() {
  const { actions } = useApp(); const mountains = useIllustration('mountains'); const city=useIllustration('city'); const desk=useIllustration('desk')
  return <div className="page"><PageHeader title="我的作品" subtitle="继续创作，管理你的写作项目" art={mountains} action={<button className="primary" onClick={() => actions.openDialog('新建作品', '已进入新建作品的 Mock 流程。正式应用层接入后可在这里填写书名、类型与初始设定。')}><Plus/>新建作品</button>}/>
    <section className="featured-project panel"><div className="featured-art" style={{ backgroundImage: `url(${city})` }}/><div><div className="title-row"><h2>迷雾之城</h2><span className="soft-tag">正在写作</span></div><p>上次停在第 18 章，人物刚回到关键场景。迷雾笼罩着港口，新的线索正在浮现。</p><div className="project-stats"><span>📖 当前章节<strong>第 18 章</strong></span><span>✎ 当前字数<strong>2,341 字</strong></span><span>◷ 最近更新<strong>今天 14:32</strong></span></div><button className="primary" onClick={() => actions.openProject('mist','writing')}><PenLine/>继续写作</button><button onClick={() => actions.openProject()}><FolderOpen/>打开作品</button></div></section>
    <div className="project-cards">{projects.slice(1).map((p) => <article className="project-card panel" key={p.id}><div className="project-thumb" style={{ backgroundImage: `url(${p.art === 'city' ? city : p.art === 'desk' ? desk : mountains})` }}/><div><div className="title-row"><h3>{p.title}</h3><span className="soft-tag">{p.status}</span></div><p>{p.subtitle}</p><small><Clock3/>最近更新：{p.updated}</small><small>📖 当前字数：{p.words.toLocaleString()} 字</small><div><button onClick={() => actions.openProject(p.id,'writing')}>继续写作</button><button onClick={() => actions.openProject(p.id)}><FolderOpen/>打开作品</button><button aria-label={`${p.title} 更多操作`} onClick={() => actions.openDialog(`${p.title} 的更多操作`, 'Mock 操作包括重命名、归档和查看项目摘要；不会修改正式作品数据。')}><MoreHorizontal/></button></div></div></article>)}</div>
  </div>
}
