import { BookOpen, Compass, FileText, PenLine } from 'lucide-react'
import { useActiveProject, useApp, useIllustration } from '../features/app/AppStore'

export function ProjectOverviewPage() {
  const { actions } = useApp(); const { project, projectState } = useActiveProject(); const art = useIllustration(project.art)
  const chapter = projectState.chapters.find((item) => item.id === projectState.activeChapterId) ?? projectState.chapters[0]
  return <div className="project-overview"><section className="featured-project panel"><div className="featured-art" style={{ backgroundImage: `url(${art})` }}/><div><div className="title-row"><h2>{project.title}</h2><span className="soft-tag">{project.status}</span></div><p>{project.subtitle}</p><div className="project-stats"><span>📖 当前章节<strong>{chapter.title}</strong></span><span>✎ 当前字数<strong>{chapter.words.toLocaleString()} 字</strong></span><span>◷ 最近更新<strong>{project.updated}</strong></span></div><button className="primary" onClick={() => actions.setProjectSection('writing')}><PenLine/>继续写作</button><button onClick={() => actions.setProjectSection('development')}><Compass/>故事发展</button></div></section><div className="overview-actions"><button className="panel" onClick={() => actions.setProjectSection('map')}><BookOpen/><span><strong>故事地图</strong><small>查看人物、剧情线与时间线</small></span></button><button className="panel" onClick={() => actions.setProjectSection('data')}><FileText/><span><strong>作品资料</strong><small>管理当前作品的设定与资料</small></span></button></div></div>
}
