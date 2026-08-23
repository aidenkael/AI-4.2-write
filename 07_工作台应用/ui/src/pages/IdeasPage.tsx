import { FileText, Lightbulb, Link, PenLine, Plus, Sparkles, Type } from 'lucide-react'
import { useState } from 'react'
import { useApp, useIllustration } from '../features/app/AppStore'
import { PageHeader } from '../components/PageHeader'

const kinds = { 场景: Type, 对白: Lightbulb, 链接: Link, 文件: FileText }
export function IdeasPage() {
  const { state, actions } = useApp(); const desk=useIllustration('desk'); const [value,setValue]=useState(''); const [filter,setFilter]=useState('全部'); const [kind,setKind]=useState<keyof typeof kinds>('场景')
  return <div className="page"><PageHeader title="灵感箱" subtitle="随时记录闪过的想法，为创作积蓄灵感能量。" art={desk}/>
    <section className="panel idea-composer"><h3><Sparkles/>快速记录灵感</h3><textarea value={value} onChange={(e)=>setValue(e.target.value)} placeholder="此刻的想法、场景或对白…" maxLength={1000}/><small>{value.length}/1000</small><div><button className={kind==='场景'?'active':''} onClick={()=>setKind('场景')}><Type/>文字</button><button className={kind==='链接'?'active':''} onClick={()=>setKind('链接')}><Link/>链接</button><button className={kind==='文件'?'active':''} onClick={()=>setKind('文件')}><FileText/>文件</button><button className="primary" onClick={async()=>{await actions.createIdea(value,kind);setValue('')}} disabled={!value.trim()}><PenLine/>记录灵感</button></div></section>
    <div className="idea-filters">{['全部','尚未使用','已用于作品'].map(x=><button key={x} className={filter===x?'active':''} onClick={()=>setFilter(x)}>{x}</button>)}</div>
    <section className="ideas-grid">{state.ideas.filter(i=>filter==='全部'||(filter==='已用于作品'?i.used:!i.used)).map((idea)=>{const Icon=kinds[idea.kind];return <article className="panel idea-card" key={idea.id}><header><span><Icon/>{idea.kind}</span><time>{idea.time}</time></header><p>{idea.content}</p><small><Sparkles/>AI 小提示：{idea.note}</small><footer><button onClick={()=>actions.notify('已保留在灵感箱，可稍后继续发展')}>♡ 先留着</button><button onClick={()=>{ actions.openProject(state.activeProjectId,'development'); actions.notify('已将灵感带入故事发展，等待你决定是否采用') }}><PenLine/>帮我发展</button><button onClick={()=>{actions.toggleIdea(idea.id);actions.notify(idea.used?'已移出作品':'已加入当前作品')}}><Plus/>{idea.used?'移出作品':'加入作品'}</button></footer></article>})}</section>
  </div>
}
