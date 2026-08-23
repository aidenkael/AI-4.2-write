import { ArrowRight, BookOpen, Clock3, Compass, Lightbulb, PenLine, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useApp, useIllustration } from '../features/app/AppStore'

export function HomePage() {
  const { actions } = useApp(); const city = useIllustration('city'); const mountains = useIllustration('mountains'); const desk = useIllustration('desk')
  const [idea, setIdea] = useState('')
  return <div className="page home-page">
    <section className="hero" style={{ backgroundImage: `linear-gradient(90deg,#eff6ff 0%,rgba(239,246,255,.88) 34%,rgba(239,246,255,.05) 68%),url(${city})` }}>
      <div><p className="eyeline"><Sparkles/>当前最值得做的事</p><h1>迷雾之城</h1><p>上次停在第 18 章，人物刚回到关键场景</p><button className="primary" onClick={() => actions.openProject('mist','writing')}><PenLine/>继续写</button></div>
    </section>
    <div className="home-grid">
      <button className="image-card" style={{ backgroundImage: `linear-gradient(180deg,rgba(255,255,255,.2),rgba(226,238,253,.15)),url(${mountains})` }} onClick={() => actions.openProject()}><h2><Compass/>故事发展</h2><p>还有 1 件事值得想清楚</p><span>继续想故事 <ArrowRight/></span></button>
      <button className="image-card" style={{ backgroundImage: `linear-gradient(180deg,rgba(255,255,255,.08),rgba(236,250,246,.18)),url(${desk})` }} onClick={() => actions.navigate('materials')}><h2><BookOpen/>素材与学习</h2><p>1 项研究刚整理完成</p><span>看看学到了什么 <ArrowRight/></span></button>
      <div className="home-side"><section className="panel quick-idea"><h2><Lightbulb/>快速记下灵感</h2><textarea value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="此刻的想法、场景或对白…"/><button onClick={async () => { await actions.createIdea(idea); setIdea('') }} disabled={!idea.trim()}><PenLine/>记录</button></section>
      <section className="panel recent"><h2><Clock3/>最近活动</h2>{['继续撰写《迷雾之城》第 18 章','整理了“城市地下通道”研究笔记','收藏了《雨夜氛围描写技巧》','记录了新的对白灵感'].map((x,i)=><p key={x}><span className={`dot d${i}`}/>{x}<time>{i ? `${i} 小时前` : '刚刚'}</time></p>)}<button className="link-button" onClick={() => actions.openDialog('全部活动', '这里会显示按时间排序的创作、学习与灵感记录。当前为前端 Mock 演示。')}>查看全部活动 <ArrowRight/></button></section></div>
    </div>
  </div>
}
