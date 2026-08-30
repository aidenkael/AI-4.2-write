import { Bot, Cloud, Folder, Image, RefreshCw, Settings as SettingsIcon, SlidersHorizontal, ScrollText } from 'lucide-react'
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
  { label: 'AI 服务 / API', Icon: Cloud }, { label: '日常 AI', Icon: Cloud }, { label: 'Agent', Icon: Bot },
  { label: '执行配置', Icon: SlidersHorizontal }, { label: '项目与数据', Icon: Folder },
  { label: '插图与视觉', Icon: Image }, { label: '高级设置', Icon: SettingsIcon },
  { label: '执行记录', Icon: ScrollText },
] as const

// 「重新检测」（环境发现）只出现在环境发现相关的分区；执行记录用「刷新记录」。
const DISCOVERY_SECTIONS: readonly SettingsSection[] = ['AI 服务 / API', 'Agent', '执行配置']

const authLabels: Record<string, string> = {
  authenticated: '已登录', configured: '已配置', not_authenticated: '未登录',
  not_detected: '未检测', unknown: '未知',
}

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
  const [section, setSection] = useState<SettingsSection>('执行配置')
  const city = useIllustration('city')
  const desk = useIllustration('desk')

  const saved = controller.data?.settings
  const savedAgentName = (id: string): string =>
    controller.agents.find((a) => a.agent_id === id)?.display_name ?? id

  return <div className="page"><PageHeader title="设置" subtitle="管理应用配置、AI 服务与个性化偏好" art={city}/><div className="settings-layout"><aside className="panel settings-menu">{menu.map(({ label, Icon }) => <button key={label} className={section === label ? 'active' : ''} onClick={() => setSection(label)}><Icon/>{label}</button>)}<div style={{ backgroundImage: `url(${desk})` }}/></aside>
    <section className="panel settings-content"><div className="section-title"><div><h2>{section}</h2><p>{section === '执行配置' ? '选择真实可用的交互桥或直接执行环境。' : '设置只显示本机实际发现的信息。'}</p></div>{DISCOVERY_SECTIONS.includes(section) ? <button onClick={controller.refresh} disabled={controller.loading}><RefreshCw/>{controller.loading ? '检测中…' : '重新检测'}</button> : null}</div>
      {controller.data ? (
        <div className="settings-savedline">
          <span className={`saved-badge ${controller.isSavedConfig ? '' : 'dirty'}`}>
            {controller.isSavedConfig ? '✓ 已保存配置' : '✎ 有未保存更改'}
          </span>
          <span className="saved-config-text">
            {saved ? savedExecutionSummary(saved, savedAgentName) : '暂无已保存的执行配置'}
          </span>
          <span className="muted-note">
            环境检测：{controller.data.discovery?.source === 'fresh' ? '本次会话已检测' : '复用上次检测'}
            {controller.data.discovery?.discovered_at ? `（${formatTime(controller.data.discovery.discovered_at)}）` : ''}
          </span>
        </div>
      ) : null}
      {controller.notice ? <div className={`settings-notice ${controller.notice.kind}`}>{controller.notice.message}</div> : null}
      {controller.loading && !controller.data ? <div className="settings-loading"><span/>正在读取本机 Agent 环境…</div> : null}
      {section === '执行配置' && controller.data ? <ExecutionModules controller={controller}/> : null}
      {section === 'Agent' && controller.data ? <div className="agent-discovery-grid">{controller.agents.map((agent) => <article className="agent-card" key={agent.agent_id}><header><span className="provider"><Bot/></span><div><h3>{agent.display_name}</h3><p>{agent.version ? `版本 ${agent.version}` : '版本未检测'}</p></div><strong className={agent.installed ? 'ok-text' : 'bad-text'}>{agent.installed ? '已安装' : '未检测'}</strong></header><p>交互桥：{agent.interactive.command_ready ? '/gowrite 已就绪' : '/gowrite 未就绪'}</p><p>直接执行：{agent.direct.available ? '可用' : '不可用'} · 认证：{authLabels[agent.direct.auth_status] ?? '未知'}</p>{agent.errors.map((error) => <small key={error}>{error}</small>)}</article>)}</div> : null}
      {section === 'AI 服务 / API' && controller.data ? <div className="real-api-settings"><div className="api-summary"><Cloud/><div><h3>本机发现的执行能力</h3><p>模型只来自可执行的本机 Agent；不会接受任意模型名或 API 地址。</p></div></div>{controller.agents.map((agent) => <article key={agent.agent_id}><strong>{agent.display_name}</strong>
        {agent.direct.model_selection === 'managed'
          ? <span>受管默认：{agent.direct.managed_model?.display_name ?? '未检测'}</span>
          : agent.direct.model_selection === 'selectable'
            ? <span>可选模型（按服务商分组）：{(agent.direct.provider_models?.length
                ? agent.direct.provider_models.map((g) => `${g.provider_id}(${g.models.filter((m) => m.selectable).length})`).join('、')
                : `${agent.direct.models.length}（受管默认）+ ${agent.direct.custom_models.length}（自定义）`)}</span>
            : <span>无可执行模型</span>}
        <em>{agent.direct.available ? '可用' : '不可用'}</em></article>)}</div> : null}
      {section === '日常 AI' ? <SemanticAiSettingsSection/> : null}
      {section === '插图与视觉' ? <VisualSettings/> : null}
      {section === '执行记录' ? <ExecutionAudits/> : null}
      {(section === '项目与数据' || section === '高级设置') ? <div className="session-config"><SlidersHorizontal size={42}/><h3>{section}</h3><p>这些界面偏好只保存在当前前端会话，不属于 Agent 执行配置。</p><label><input type="checkbox" checked={state.preferences.sound} onChange={(event) => actions.setPreference('sound', event.target.checked)}/> 在执行完成/失败时播放提示音</label><p className="muted-note">任务完成或失败时显示全局通知；开启提示音后会同时播放一段短提示音（本机音量控制）。</p></div> : null}
    </section></div></div>
}
