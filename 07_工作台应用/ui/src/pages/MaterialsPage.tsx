import { BookOpen, MessageSquare, PenLine, Play, Plus, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { materials } from '../mock/data'
import { useIllustration } from '../features/app/AppStore'

export function MaterialsPage() {
  const [selected, setSelected] = useState(materials[2]); const [tab, setTab] = useState('全部'); const mountains=useIllustration('mountains')
  const tabs = ['全部','参考作品','专题研究','已学会','处理中','需要处理']
  return <div className="page"><PageHeader title="素材与学习" subtitle="在这里添加、整理并研究素材，让 AI 从你的资料中学习，写出更好的作品。" art={mountains}/>
    <div className="filterbar panel">{tabs.map((x)=><button key={x} className={tab===x?'active':''} onClick={()=>setTab(x)}>{x}</button>)}<button className="primary"><Plus/>添加素材 / 发起研究</button></div>
    <div className="split materials-layout"><section className="panel material-list"><h3>全部素材与研究 <small>（{materials.length}）</small></h3>{materials.filter((m)=>tab==='全部'||m.type===tab||m.status===tab).map((m)=><button key={m.id} className={selected.id===m.id?'selected':''} onClick={()=>setSelected(m)}><span className="material-thumb">{m.type==='专题研究'?'研':'书'}</span><span><strong>{m.title}</strong><small>{m.type}　·　{m.date}</small></span><em>{m.status}</em></button>)}</section>
    <section className="panel material-detail"><div className="detail-title"><span className="material-thumb large">研</span><div><h2>{selected.title} <PenLine size={17}/></h2><p>{selected.type}　更新于 {selected.date}</p></div><span className="soft-tag">{selected.status}</span></div><div className="learning"><h3><Sparkles/>AI 从这里学到了什么</h3><p>{selected.summary}</p><ul>{selected.knowledge.map((x)=><li key={x}>{x}</li>)}</ul><div><button><BookOpen/>查看研究稿</button><button><Play/>继续学习</button><button><MessageSquare/>问 AI</button></div></div><h3><Sparkles/>已学会的知识</h3><div className="knowledge-grid">{selected.knowledge.map((x,i)=><article key={x}><strong>{x}</strong><p>{['可复用的视觉与叙事特征。','帮助组织城市空间和人物处境。','用于控制主题、情绪与节奏。'][i]}</p></article>)}</div></section></div>
  </div>
}
