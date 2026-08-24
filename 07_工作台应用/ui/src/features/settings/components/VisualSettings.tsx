import { Image, RotateCcw } from 'lucide-react'
import { useRef, useState } from 'react'
import { illustrationLabels } from '../../../assets/illustrations'
import type { IllustrationKey } from '../../../contracts/ui'
import { useApp } from '../../app/AppStore'

export function VisualSettings() {
  const { state, actions } = useApp()
  const input = useRef<HTMLInputElement>(null)
  const [target, setTarget] = useState<IllustrationKey>('city')
  const upload = (file?: File) => { if (file) actions.setIllustration(target, URL.createObjectURL(file)) }
  return <div className="illustration-settings"><div className="illustration-tabs">{(Object.keys(illustrationLabels) as IllustrationKey[]).map((key) => <button key={key} className={target === key ? 'active' : ''} onClick={() => setTarget(key)}>{illustrationLabels[key]}</button>)}</div><div className="illustration-preview" style={{ backgroundImage: `url(${state.illustrations.custom[target] ?? state.illustrations.defaults[target]})` }}/><input ref={input} hidden type="file" accept="image/*" onChange={(event) => upload(event.target.files?.[0])}/><div><button className="primary" onClick={() => input.current?.click()}><Image/>更换自定义图片</button><button onClick={() => { actions.resetIllustration(target); actions.notify(`${illustrationLabels[target]}已恢复默认插图`) }}><RotateCcw/>恢复默认</button></div></div>
}
