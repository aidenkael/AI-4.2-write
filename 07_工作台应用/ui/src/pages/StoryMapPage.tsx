import { BookOpen, ChevronDown, Info, MessageSquare, Settings } from 'lucide-react'
import { useState } from 'react'
import { EmptyAvatar } from '../components/EmptyAvatar'
import { characters } from '../mock/data'
import { useIllustration } from '../features/app/AppStore'

export function StoryMapPage() {
  const [tab,setTab]=useState('人物关系'); const [selected,setSelected]=useState(characters[0]); const mountains=useIllustration('mountains')
  return <div className="panel map-page"><header className="map-tabs">{['人物关系','剧情线','时间线','伏笔与问题'].map(x=><button className={tab===x?'active':''} onClick={()=>setTab(x)} key={x}>{x}</button>)}<span/><button><Settings/>视图设置<ChevronDown/></button><button><Info/>图例说明</button></header>
    {tab==='人物关系'?<div className="map-content"><section className="network" style={{backgroundImage:`linear-gradient(rgba(255,255,255,.84),rgba(255,255,255,.84)),url(${mountains})`}}>{characters.map((c,i)=><button key={c.id} className={`node node-${i} ${selected.id===c.id?'selected':''}`} onClick={()=>setSelected(c)}><EmptyAvatar name={c.name} color={c.color}/><span><strong>{c.name}</strong><small>{c.identity}</small><em>{c.role}</em></span></button>)}<svg className="connections" viewBox="0 0 900 620"><path d="M450 300L450 105M420 300L150 300M480 300L750 300M420 335L250 510M480 335L665 510"/><text x="300" y="286">合作调查</text><text x="590" y="286">利益交换</text><text x="360" y="435">旧识</text><text x="550" y="435">怀疑</text></svg><div className="legend"><span>— 密切关系</span><span>— 一般关系</span><span>--- 较弱关系</span></div></section><aside className="character-inspector"><EmptyAvatar name={selected.name} color={selected.color} large/><div><h2>{selected.name} <span className="soft-tag">{selected.role}</span></h2><p>{selected.identity}</p><strong>当前状态：{selected.status}</strong><blockquote>“真相像雾一样，越靠近，越看不清。”</blockquote></div><hr/><h3>最近变化</h3><p>• 在第18章中发现了港城旧影的关键照片，开始怀疑旧案与当前事件有关。</p><h3>相关人物</h3><div className="mini-people">{characters.filter(c=>c.id!==selected.id).slice(0,4).map(c=><button key={c.id} onClick={()=>setSelected(c)}><EmptyAvatar name={c.name} color={c.color}/>{c.name}</button>)}</div><button className="primary wide"><BookOpen/>查看相关章节</button><button className="wide"><MessageSquare/>问 AI 关于这个人物</button></aside></div>:<div className="map-placeholder"><h2>{tab}</h2><p>已切换到 {tab} 视图。Mock 演示保留同一信息架构，人物关系图是当前主视图。</p></div>}
  </div>
}
