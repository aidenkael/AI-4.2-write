import { Bot, Check, RefreshCw, Wifi, XCircle } from 'lucide-react'
import type { ExecutionMode } from '../../../bridge/client'
import type { SettingsController } from '../useSettingsController'

const Status = ({ ok, yes, no }: { ok: boolean; yes: string; no: string }) => (
  <span className={`settings-status ${ok ? 'ok' : 'bad'}`}>{ok ? <Check /> : <XCircle />}{ok ? yes : no}</span>
)

const authLabels: Record<string, string> = {
  authenticated: '已登录', configured: '已配置', not_authenticated: '未登录',
  not_detected: '未检测', unknown: '未知',
}

const cliKindLabels: Record<string, string> = {
  current_cli: '当前 CLI', legacy_qodercli: '旧版 CLI（兼容）', not_detected: '未检测',
}

const EnvironmentEvidence = ({ label, version, status, path }: {
  label: string; version?: string | null; status: string; path?: string | null
}) => <div className="environment-evidence">
  <span><strong>{label}</strong>{version ? ` ${version}` : ''} · {status}</span>
  {path ? <code title={path}>{path}</code> : null}
</div>

export function ExecutionModules({ controller }: { controller: SettingsController }) {
  const {
    draft, agents, interactiveAgent, directAgent, directProfile, connection,
    testing, saving, directValid, interactiveValid, canSave, update, refresh, save, test,
  } = controller
  if (!draft) return null

  const selectedModelAvailable = directProfile?.models.some((model) => model.id === draft.direct_model) ?? false
  return <div className="execution-settings">
    <section className="mode-choice">
      <div><h3>默认执行方式</h3><p>交互桥在 Agent 会话中执行；直接执行由 Go Write 调用本机 Agent adapter。</p></div>
      <div className="segmented-control">{([
        ['interactive_bridge', '交互桥'], ['direct', '直接执行'],
      ] as Array<[ExecutionMode, string]>).map(([mode, label]) => <button key={mode} className={draft.default_execution_mode === mode ? 'active' : ''} onClick={() => update('default_execution_mode', mode)}>{label}</button>)}</div>
    </section>

    <article className={`execution-card ${draft.default_execution_mode === 'interactive_bridge' ? 'selected' : ''}`}>
      <header><span className="provider p0"><Bot /></span><div><h3>A. 交互桥模式</h3><p>任务准备好后，在所选 Agent 会话输入 <code>/gowrite</code>，结果返回 Go Write。</p></div><button onClick={refresh}><RefreshCw />重新检测</button></header>
      <div className="execution-form"><label>执行 Agent<select value={draft.interactive_agent} onChange={(event) => update('interactive_agent', event.target.value)}>{agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.display_name}</option>)}</select></label>
        <div className="status-grid"><Status ok={Boolean(interactiveAgent?.interactive.available)} yes="Desktop 已检测" no="Desktop 未检测"/><Status ok={Boolean(interactiveAgent?.interactive.bridge_ready)} yes="桥已就绪" no="桥未就绪"/><Status ok={Boolean(interactiveAgent?.interactive.command_ready)} yes="/gowrite 可用" no="/gowrite 不可用"/></div>
      </div>
      {interactiveAgent?.desktop ? <EnvironmentEvidence
        label="Qoder Desktop"
        version={interactiveAgent.desktop.version}
        status={interactiveAgent.desktop.installed ? '已安装' : '未检测'}
        path={interactiveAgent.desktop.path}
      /> : null}
      {interactiveAgent?.interactive.repair_hint ? <p className="settings-warning">{interactiveAgent.interactive.repair_hint}</p> : null}
      {!interactiveValid ? <small>当前选择不会被标记为可执行，保存后也不会伪装成已连接。</small> : null}
    </article>

    <article className={`execution-card ${draft.default_execution_mode === 'direct' ? 'selected' : ''}`}>
      <header><span className="provider p1"><Wifi /></span><div><h3>B. 直接执行模式</h3><p>按 Agent → 本机执行配置 → 可选模型的真实发现顺序运行。</p></div><button onClick={refresh}><RefreshCw />重新检测</button></header>
      <div className="execution-form direct-fields">
        <label>执行 Agent<select value={draft.direct_agent} onChange={(event) => { update('direct_agent', event.target.value); update('direct_profile_id', null); update('direct_model', null) }}>{agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.display_name}</option>)}</select></label>
        <label>执行配置<select value={draft.direct_profile_id ?? ''} onChange={(event) => { update('direct_profile_id', event.target.value || null); update('direct_model', null) }}><option value="">请选择本机配置</option>{directAgent?.direct.execution_profiles.map((profile) => <option key={profile.id} value={profile.id} disabled={!profile.available}>{profile.display_name}{profile.available ? '' : '（不可用）'}</option>)}{draft.direct_profile_id && !directProfile ? <option value={draft.direct_profile_id}>已保存但当前不可用：{draft.direct_profile_id}</option> : null}</select></label>
        {directProfile?.model_selection === 'selectable' ? <label>模型<select value={draft.direct_model ?? ''} onChange={(event) => update('direct_model', event.target.value || null)}><option value="">请选择可用模型</option>{directProfile.models.filter((model) => model.selectable).map((model) => <option key={model.id} value={model.id}>{model.display_name}</option>)}{draft.direct_model && !selectedModelAvailable ? <option value={draft.direct_model}>已保存但当前不可用：{draft.direct_model}</option> : null}</select></label> : null}
        {directProfile?.model_selection === 'managed' ? <div className="managed-model"><span>模型</span><strong>由 Agent 管理{directProfile.models[0] ? `：${directProfile.models[0].display_name}` : ''}</strong></div> : null}
        {directProfile?.reasoning_effort_options?.length ? <label>思考强度<select value={draft.reasoning_effort ?? ''} onChange={(event) => update('reasoning_effort', event.target.value || null)}><option value="">由 Agent 默认</option>{directProfile.reasoning_effort_options.map((effort) => <option key={effort} value={effort}>{effort}</option>)}</select></label> : null}
      </div>
      {directAgent?.cli ? <EnvironmentEvidence
        label="Qoder CLI"
        version={directAgent.cli.version}
        status={`${cliKindLabels[directAgent.cli.kind] ?? directAgent.cli.kind} · ${directAgent.cli.usable ? '入口可用' : '入口不可用'}`}
        path={directAgent.cli.path}
      /> : null}
      <div className="direct-status"><Status ok={Boolean(directAgent?.direct.available)} yes="直接执行可用" no="直接执行不可用"/><span>认证状态：{authLabels[directAgent?.direct.auth_status ?? 'not_detected'] ?? '未知'}</span>{directProfile?.error ? <span className="settings-warning">{directProfile.error}</span> : null}</div>
      <footer><button onClick={test} disabled={!directValid || testing}><Wifi />{testing ? '检查中…' : '测试连接'}</button>{connection ? <span className={`connection-result ${connection.status}`}>{connection.message}</span> : null}</footer>
    </article>

    <div className="settings-savebar"><span>{canSave ? '当前默认模式配置有效' : '当前默认模式尚未就绪，请选择可用配置'}</span><button className="primary" onClick={save} disabled={!canSave || saving}>{saving ? '保存中…' : '保存执行设置'}</button></div>
  </div>
}
