import { BookOpen, Clock3, Edit3, FileCheck2, Folder, Globe2, MapPin, Plus, Search, Star, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { EmptyAvatar } from '../components/EmptyAvatar'
import { characters } from '../mock/data'
import { useApp, useIllustration } from '../features/app/AppStore'

const cats = [['人物', UserRound], ['地点', MapPin], ['世界与规则', Globe2], ['重要事件', Star], ['已确认设定', FileCheck2], ['项目资料', Folder]] as const
const records: Record<string, Array<{ title: string; summary: string; meta: string }>> = {
  '地点': [{ title: '雾城旧城区', summary: '港口、旧仓库与斑驳铁轨交错的核心场景。', meta: '地点' }, { title: '港务局', summary: '掌握港口异动记录的官方机构。', meta: '地点' }],
  '世界与规则': [{ title: '港城迷雾', summary: '雨夜会加重，能遮蔽部分旧城视线。', meta: '世界规则' }, { title: '夜幕组织', summary: '围绕古老文献活动的隐秘组织。', meta: '组织' }],
  '重要事件': [{ title: '雾潮异动事件', summary: '港口突发迷雾，调查由此开始。', meta: '第1章' }, { title: '旧影照片出现', summary: '林砚取得 1943 年码头照片。', meta: '第18章' }],
  '已确认设定': [{ title: '守夜人公会条款', summary: '已确认的港城守夜制度与职责。', meta: '设定' }, { title: '林砚的继承身份', summary: '林砚与港城图书馆旧案存在关联。', meta: '人物设定' }],
  '项目资料': [{ title: '章节节奏备忘', summary: '当前章保持悬疑与人物关系并行推进。', meta: '项目资料' }, { title: '创作意图', summary: '以旧港谜案承载人物选择与代价。', meta: '项目资料' }],
}

export function ProjectDataPage() {
  const { actions } = useApp(); const [cat, setCat] = useState('人物'); const [selected, setSelected] = useState(characters[0]); const [query, setQuery] = useState('')
  const entries = useMemo(() => cat === '人物' ? characters.filter((item) => item.name.includes(query)) : (records[cat] ?? []).filter((item) => item.title.includes(query) || item.summary.includes(query)), [cat, query])
  return <div className="data-layout"><aside className="panel data-menu"><button className="primary" onClick={() => actions.openDialog('新建资料', `已打开「${cat}」资料的 Mock 新建流程。`)}><Plus/>新建资料</button>{cats.map(([label, Icon]) => <button key={label} className={cat === label ? 'active' : ''} onClick={() => { setCat(label); setQuery('') }}><Icon/>{label}</button>)}<div style={{ backgroundImage: `url(${useIllustration('mountains')})` }}/></aside>
    <section className="panel data-main"><header><h2>{cat} <small>共 {cat === '人物' ? 18 : entries.length} 项</small></h2><label><Search/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`搜索${cat}`}/></label></header>{cat === '人物' ? (entries as typeof characters).map((character) => <article key={character.id} className={selected.id === character.id ? 'selected' : ''} onClick={() => setSelected(character)}><EmptyAvatar name={character.name} color={character.color} large/><div><h2>{character.name} <span className="soft-tag">{character.role}</span></h2><p><b>身份：</b>{character.identity}</p><p><b>当前状态：</b>{character.status}</p><p><b>相关关系：</b>{character.relation}</p><p><b>备注：</b>{character.note}</p></div><span>出场：第 {character.id === 'lu' ? '2' : '1'} 章<button onClick={(event) => { event.stopPropagation(); actions.openProject('mist', 'writing') }}><BookOpen/>查看相关章节</button><button onClick={(event) => { event.stopPropagation(); actions.openDialog('编辑资料', `正在编辑「${character.name}」的 Mock 人物资料。`) }}><Edit3/>编辑资料</button></span></article>) : (entries as Array<{ title: string; summary: string; meta: string }>).map((item) => <article key={item.title} className="record-item" onClick={() => actions.openDialog(item.title, item.summary)}><span className="record-icon">☆</span><div><h2>{item.title}</h2><p>{item.summary}</p><small>{item.meta}</small></div><span><button onClick={(event) => { event.stopPropagation(); actions.openDialog('编辑资料', `正在编辑「${item.title}」的 Mock 资料。`) }}><Edit3/>编辑资料</button></span></article>)}{entries.length === 0 && <div className="empty-state">没有匹配的{cat}资料</div>}</section>
    <aside className="panel recent-data"><h2><Clock3/>最近更新的资料</h2>{[selected, ...characters.filter((character) => character.id !== selected.id).slice(0, 2)].map((character) => <button key={character.id} onClick={() => { setCat('人物'); setSelected(character) }}><EmptyAvatar name={character.name} color={character.color}/><span><strong>{character.name}</strong><small>人物　·　编辑者：你</small></span><time>今天</time></button>)}<button onClick={() => { setCat('重要事件'); setQuery('') }}><span className="record-icon">☆</span><span><strong>雾潮异动事件</strong><small>重要事件　·　编辑者：你</small></span></button><button className="wide" onClick={() => actions.openDialog('全部资料更新', '这里将按时间显示全部资料变更记录。')}>查看全部资料更新 →</button></aside>
  </div>
}
