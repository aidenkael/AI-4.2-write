import { BookOpen, Clock3, Edit3, FileCheck2, Folder, Globe2, MapPin, Plus, Search, Star, UserRound } from 'lucide-react'
import { useState } from 'react'
import { EmptyAvatar } from '../components/EmptyAvatar'
import { characters } from '../mock/data'
import { useIllustration } from '../features/app/AppStore'

const cats=[['人物',UserRound],['地点',MapPin],['世界与规则',Globe2],['重要事件',Star],['已确认设定',FileCheck2],['项目资料',Folder]] as const
export function ProjectDataPage() {
  const [cat,setCat]=useState('人物'); const [selected,setSelected]=useState(characters[0]); const [query,setQuery]=useState('')
  return <div className="data-layout"><aside className="panel data-menu"><button className="primary"><Plus/>新建资料</button>{cats.map(([x,Icon])=><button key={x} className={cat===x?'active':''} onClick={()=>setCat(x)}><Icon/>{x}</button>)}<div style={{backgroundImage:`url(${useIllustration('mountains')})`}}/></aside>
    <section className="panel data-main"><header><h2>{cat} <small>共 {cat==='人物'?'18':'6'} 项</small></h2><label><Search/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder={`搜索${cat}`}/></label></header>{cat==='人物'?characters.filter(c=>c.name.includes(query)).map(c=><article key={c.id} className={selected.id===c.id?'selected':''} onClick={()=>setSelected(c)}><EmptyAvatar name={c.name} color={c.color} large/><div><h2>{c.name} <span className="soft-tag">{c.role}</span></h2><p><b>身份：</b>{c.identity}</p><p><b>当前状态：</b>{c.status}</p><p><b>相关关系：</b>{c.relation}</p><p><b>备注：</b>{c.note}</p></div><span>出场：第 {c.id==='lu'?'2':'1'} 章<button><BookOpen/>查看相关章节</button><button onClick={(e)=>{e.stopPropagation();setSelected(c)}}><Edit3/>编辑资料</button></span></article>):<div className="category-placeholder"><h2>{cat}</h2><p>已切换资料分类。这里的条目与选择仅修改前端 Mock 状态。</p></div>}</section>
    <aside className="panel recent-data"><h2><Clock3/>最近更新的资料</h2>{[selected,...characters.filter(c=>c.id!==selected.id).slice(0,2)].map(c=><button key={c.id} onClick={()=>setSelected(c)}><EmptyAvatar name={c.name} color={c.color}/><span><strong>{c.name}</strong><small>人物　·　编辑者：你</small></span><time>今天</time></button>)}<button><span className="record-icon">☆</span><span><strong>雾潮异动事件</strong><small>重要事件　·　编辑者：你</small></span></button><button className="wide">查看全部资料更新 →</button></aside>
  </div>
}
