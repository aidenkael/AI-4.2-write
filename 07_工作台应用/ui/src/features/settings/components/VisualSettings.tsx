import { Image, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { illustrationLabels } from '../../../assets/illustrations'
import type { IllustrationKey } from '../../../contracts/ui'
import { useApp } from '../../app/AppStore'

export function VisualSettings() {
  const { state, actions } = useApp()
  const [target, setTarget] = useState<IllustrationKey>('city')
  const upload = async () => {
    try { await actions.setIllustration(target); actions.notify(`${illustrationLabels[target]}已更新`) } catch (error) { actions.notify(error instanceof Error ? error.message : String(error)) }
  }
  const reset = async () => {
    try { await actions.resetIllustration(target); actions.notify(`${illustrationLabels[target]}已恢复默认插图`) } catch (error) { actions.notify(error instanceof Error ? error.message : String(error)) }
  }
  return <div className="illustration-settings"><div className="illustration-tabs">{(Object.keys(illustrationLabels) as IllustrationKey[]).map((key) => <button key={key} className={target === key ? 'active' : ''} onClick={() => setTarget(key)}>{illustrationLabels[key]}</button>)}</div><div className="illustration-preview" style={{ backgroundImage: `url(${state.illustrations.custom[target] ?? state.illustrations.defaults[target]})` }}/><div><button className="primary" onClick={() => void upload()}><Image/>选择本地图片 / 更换</button><button onClick={() => void reset()}><RotateCcw/>恢复默认</button></div></div>
}
