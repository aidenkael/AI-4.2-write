import { Bell, Cloud, RefreshCw, ScrollText } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../../components/PageHeader'
import { useApp, useIllustration } from '../app/AppStore'
import { ExecutionAudits } from './components/ExecutionAudits'
import { SemanticAiSettingsSection } from './components/SemanticAiSettings'
import { ExecutionModules } from './components/ExecutionModules'
import { VisualSettings } from './components/VisualSettings'
import { savedExecutionSummary } from './settingsSummary'
import type { SettingsSection } from './types'
import { useSettingsController } from './useSettingsController'

const menu = [
  { label: 'AI 与执行', Icon: Cloud }, { label: '界面与通知', Icon: Bell },
  { label: '执行记录', Icon: ScrollText },
] as const

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function SettingsFeature() {
  const controller = useSettingsController()
  const { state, actions } = useApp()
  const [section, setSection] = useState<SettingsSection>('AI 与执行')
  const city = useIllustration('city')
  const desk = useIllustration('desk')

  const saved = controller.data?.settings
  const savedAgentName = (id: string): string =>
    controller.agents.find((a) => a.agent_id === id)?.display_name ?? id

  return <div className="page"><PageHeader title="设置" subtitle="配置更新作品状态、创作任务执行与本次会话的界面通知。" art={city}/><div className="settings-layout"><aside className="panel settings-menu">{menu.map(({ label, Icon }) => <button key={label} className={section === label ? 'active' : ''} onClick={() => setSection(label)}><Icon/>{label}</button>)}<div style={{ backgroundImage: `url(${desk})` }}/></aside>
    <section className="panel settings-content">
      {section === 'AI 与执行' ? <>
        <div className="section-title"><div><h2>AI 与执行</h2><p>分别配置「更新作品状态」的日常 AI，以及创作任务的 Agent 执行方式。</p></div></div>
        <div className="settings-group"><div className="settings-group-title"><h3>日常 AI / 更新作品状态</h3><p>用于你明确发起的有界语义整理，不参与创作任务执行。</p></div><SemanticAiSettingsSection/></div>
        <div className="settings-group"><div className="settings-group-title execution-group-header"><div><h3>创作任务执行</h3><p>选择交互桥或直接执行，并查看所选 Agent 的真实环境信息。</p></div><button onClick={controller.refresh} disabled={controller.loading}><RefreshCw/>{controller.loading ? '检测中…' : '重新检测'}</button></div>
          {controller.data ? <div className="settings-savedline"><span className={`saved-badge ${controller.isSavedConfig ? '' : 'dirty'}`}>{controller.isSavedConfig ? '✓ 已保存配置' : '✎ 有未保存更改'}</span><span className="saved-config-text">{saved ? savedExecutionSummary(saved, savedAgentName) : '暂无已保存的执行配置'}</span><span className="muted-note">环境检测：{controller.data.discovery?.source === 'fresh' ? '本次会话已检测' : '复用上次检测'}{controller.data.discovery?.discovered_at ? `（${formatTime(controller.data.discovery.discovered_at)}）` : ''}</span></div> : null}
          {controller.notice ? <div className={`settings-notice ${controller.notice.kind}`}>{controller.notice.message}</div> : null}
          {controller.loading && !controller.data ? <div className="settings-loading"><span/>正在读取本机 Agent 环境…</div> : null}
          {controller.data ? <ExecutionModules controller={controller}/> : null}
        </div>
      </> : null}
      {section === '界面与通知' ? <><div className="section-title"><div><h2>界面与通知</h2><p>以下界面偏好仅在本次 Go Write 会话中生效，重新启动后恢复默认。</p></div></div><div className="settings-group"><div className="settings-group-title"><h3>插图与视觉</h3><p>为当前会话替换页面插图，随重启恢复默认。</p></div><VisualSettings/></div><div className="settings-group session-preferences"><div className="settings-group-title"><h3>通知</h3><p>任务完成或失败时显示全局通知；提示音使用本机音量。</p></div><label><input type="checkbox" checked={state.preferences.sound} onChange={(event) => actions.setPreference('sound', event.target.checked)}/> 在执行完成/失败时播放提示音</label></div></> : null}
      {section === '执行记录' ? <><div className="section-title"><div><h2>执行记录</h2><p>本地只读诊断信息，不影响 AI 或执行配置。</p></div></div><ExecutionAudits/></> : null}
    </section></div></div>
}
