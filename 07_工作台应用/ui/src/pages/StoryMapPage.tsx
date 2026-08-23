import { BookOpen, ChevronDown, Info, MessageSquare, Settings } from 'lucide-react'
import { useState } from 'react'
import { EmptyAvatar } from '../components/EmptyAvatar'
import { characters } from '../mock/data'
import { useApp, useIllustration } from '../features/app/AppStore'

const overview = {
  '剧情线': [['旧案线索', '林砚在港城旧影中发现关键照片。', '第18章'], ['夜幕组织', '盟友立场开始出现分歧。', '待推进'], ['港口异动', '港务局的调查范围扩大。', '第19章']],
  '时间线': [['1943 年', '港城码头送别事件。', '过去'], ['三日前', '林砚收到匿名照片。', '已发生'], ['今晚', '进入旧仓库核对线索。', '当前']],
  '伏笔与问题': [['父亲的旧案', '照片背面的署名尚未解读。', '未解决'], ['迷雾现象', '迷雾与古老文献的关系。', '未解决'], ['陆沉的立场', '是否知晓港务局内幕。', '观察中']],
} as const

export function StoryMapPage() {
  const { actions } = useApp()
  const [tab, setTab] = useState<'人物关系' | keyof typeof overview>('人物关系')
  const [selected, setSelected] = useState(characters[0])
  const mountains = useIllustration('mountains')
  return <div className="panel map-page"><header className="map-tabs">{(['人物关系', '剧情线', '时间线', '伏笔与问题'] as const).map((item) => <button className={tab === item ? 'active' : ''} onClick={() => setTab(item)} key={item}>{item}</button>)}<span/><button onClick={() => actions.openDialog('视图设置', '当前 Mock 可切换关系、剧情、时间线与伏笔视图；布局设置将在正式应用层持久化。')}><Settings/>视图设置<ChevronDown/></button><button onClick={() => actions.openDialog('图例说明', '实线表示密切关系，细线表示一般关系，虚线表示较弱或待确认关系。')}><Info/>图例说明</button></header>
    {tab === '人物关系' ? <div className="map-content"><section className="network" style={{ backgroundImage: `linear-gradient(rgba(255,255,255,.84),rgba(255,255,255,.84)),url(${mountains})` }}>{characters.map((character, index) => <button key={character.id} className={`node node-${index} ${selected.id === character.id ? 'selected' : ''}`} onClick={() => setSelected(character)}><EmptyAvatar name={character.name} color={character.color}/><span><strong>{character.name}</strong><small>{character.identity}</small><em>{character.role}</em></span></button>)}<svg className="connections" viewBox="0 0 900 620"><path d="M450 300L450 105M420 300L150 300M480 300L750 300M420 335L250 510M480 335L665 510"/><text x="300" y="286">合作调查</text><text x="590" y="286">利益交换</text><text x="360" y="435">旧识</text><text x="550" y="435">怀疑</text></svg><div className="legend"><span>— 密切关系</span><span>— 一般关系</span><span>--- 较弱关系</span></div></section><aside className="character-inspector"><EmptyAvatar name={selected.name} color={selected.color} large/><div><h2>{selected.name} <span className="soft-tag">{selected.role}</span></h2><p>{selected.identity}</p><strong>当前状态：{selected.status}</strong><blockquote>“真相像雾一样，越靠近，越看不清。”</blockquote></div><hr/><h3>最近变化</h3><p>• 在第18章中发现了港城旧影的关键照片，开始怀疑旧案与当前事件有关。</p><h3>相关人物</h3><div className="mini-people">{characters.filter((character) => character.id !== selected.id).slice(0, 4).map((character) => <button key={character.id} onClick={() => setSelected(character)}><EmptyAvatar name={character.name} color={character.color}/>{character.name}</button>)}</div><button className="primary wide" onClick={() => actions.setProjectSection('writing')}><BookOpen/>查看相关章节</button><button className="wide" onClick={() => actions.openDialog('问 AI 关于这个人物', `围绕「${selected.name}」的 Mock 问答已准备好。`)}><MessageSquare/>问 AI 关于这个人物</button></aside></div> : <section className="map-overview">{overview[tab].map(([title, detail, status]) => <button className="map-overview-card" key={title} onClick={() => actions.openDialog(title, detail)}><span className="soft-tag">{status}</span><h2>{title}</h2><p>{detail}</p><small>点击查看 Mock 详情</small></button>)}</section>}
  </div>
}
