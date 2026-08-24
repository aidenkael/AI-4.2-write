import { Bot, Cloud, Folder, Image, KeyRound, RefreshCw, Settings as SettingsIcon, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../../components/PageHeader'
import { useApp, useIllustration } from '../app/AppStore'
import { ExecutionModules } from './components/ExecutionModules'
import { VisualSettings } from './components/VisualSettings'
import type { SettingsSection } from './types'
import { useSettingsController } from './useSettingsController'

const menu = [
  { label: 'AI 服务 / API', Icon: Cloud }, { label: 'Agent', Icon: Bot },
  { label: '执行配置', Icon: SlidersHorizontal }, { label: '项目与数据', Icon: Folder },
  { label: '插图与视觉', Icon: Image }, { label: '高级设置', Icon: SettingsIcon },
] as const

const authLabels: Record<string, string> = {
  authenticated: '已登录', configured: '已配置', not_authenticated: '未登录',
  not_detected: '未检测', unknown: '未知',
}

export function SettingsFeature() {
  const controller = useSettingsController()
  const { state, actions } = useApp()
  const [section, setSection] = useState<SettingsSection>('执行配置')
  const [token, setToken] = useState('')
  const city = useIllustration('city')
  const desk = useIllustration('desk')
  const hasByok = controller.agents.some((agent) => agent.direct.execution_profiles.some((profile) => profile.type === 'byok'))

  return <div className="page"><PageHeader title="设置" subtitle="管理应用配置、AI 服务与个性化偏好" art={city}/><div className="settings-layout"><aside className="panel settings-menu">{menu.map(({ label, Icon }) => <button key={label} className={section === label ? 'active' : ''} onClick={() => setSection(label)}><Icon/>{label}</button>)}<div style={{ backgroundImage: `url(${desk})` }}/></aside>
    <section className="panel settings-content"><div className="section-title"><div><h2>{section}</h2><p>{section === '执行配置' ? '选择真实可用的交互桥或直接执行环境。' : '设置只显示本机实际发现的信息。'}</p></div>{section !== '插图与视觉' ? <button onClick={controller.refresh} disabled={controller.loading}><RefreshCw/>{controller.loading ? '检测中…' : '刷新状态'}</button> : null}</div>
      {controller.notice ? <div className={`settings-notice ${controller.notice.kind}`}>{controller.notice.message}</div> : null}
      {controller.loading && !controller.data ? <div className="settings-loading"><span/>正在读取本机 Agent 环境…</div> : null}
      {section === '执行配置' && controller.data ? <ExecutionModules controller={controller}/> : null}
      {section === 'Agent' && controller.data ? <div className="agent-discovery-grid">{controller.agents.map((agent) => <article className="agent-card" key={agent.agent_id}><header><span className="provider"><Bot/></span><div><h3>{agent.display_name}</h3><p>{agent.version ? `版本 ${agent.version}` : '版本未检测'}</p></div><strong className={agent.installed ? 'ok-text' : 'bad-text'}>{agent.installed ? '已安装' : '未检测'}</strong></header><p>交互桥：{agent.interactive.command_ready ? '/gowrite 已就绪' : '/gowrite 未就绪'}</p><p>直接执行：{agent.direct.available ? '可用' : '不可用'} · 认证：{authLabels[agent.direct.auth_status] ?? '未知'}</p>{agent.errors.map((error) => <small key={error}>{error}</small>)}</article>)}</div> : null}
      {section === 'AI 服务 / API' && controller.data ? <div className="real-api-settings"><div className="api-summary"><Cloud/><div><h3>本机发现的执行配置</h3><p>模型和 provider 只来自已安装 Agent；不会接受任意模型名。</p></div></div>{controller.agents.flatMap((agent) => agent.direct.execution_profiles).map((profile) => <article key={`${profile.type}-${profile.id}`}><strong>{profile.display_name}</strong><span>{profile.provider_id ?? profile.type}</span><em>{profile.available ? '可用' : '不可用'}</em></article>)}{hasByok ? <div className="secret-entry"><KeyRound/><label>BYOK 凭据<input type="password" autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} placeholder={controller.data.byok.has_secret ? '已安全保存；输入新值可替换' : '输入 Token（保存后不再显示）'}/></label><button onClick={async () => { await controller.saveSecret(token); setToken('') }} disabled={!token.trim()}>安全保存</button>{controller.data.byok.has_secret ? <button onClick={controller.deleteSecret}>删除凭据</button> : null}</div> : <p className="settings-warning">当前安装没有公开可用的 BYOK 执行配置，因此不显示凭据输入。</p>}</div> : null}
      {section === '插图与视觉' ? <VisualSettings/> : null}
      {(section === '项目与数据' || section === '高级设置') ? <div className="mock-config"><SlidersHorizontal size={42}/><h3>{section}</h3><p>这些界面偏好仍保存在当前前端会话，不属于 Agent 执行配置。</p><label><input type="checkbox" checked={state.preferences.autosave} onChange={(event) => actions.setPreference('autosave', event.target.checked)}/> 启用自动保存提示</label><label><input type="checkbox" checked={state.preferences.sound} onChange={(event) => actions.setPreference('sound', event.target.checked)}/> 在执行完成时播放提示音</label><button onClick={() => actions.notify(`${section}界面偏好已更新`)}>保存界面偏好</button></div> : null}
    </section></div></div>
}
