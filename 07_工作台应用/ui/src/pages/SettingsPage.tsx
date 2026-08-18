import { useEffect, useMemo, useState } from 'react'
import {
  deleteByokSecret,
  getAgentOptions,
  getAgentSettings,
  saveAgentSettings,
  saveByokSecret,
  testAgentConnection,
  type AgentOptionsData,
  type AgentSettingsData,
  type ConnectionTestResult,
} from '../bridge/client'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; settings: AgentSettingsData; options: AgentOptionsData }
  | { kind: 'error'; message: string }

const AGENT_LABELS: Record<string, string> = {
  deepseek_harness: 'DeepSeek Harness',
  qoder: 'Qoder',
}

export default function SettingsPage() {
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' })

  // 表单（由后端已保存设置初始化）
  const [agent, setAgent] = useState('qoder')
  const [qoderMode, setQoderMode] = useState('qoder_native')
  const [qoderModel, setQoderModel] = useState('')
  const [reasoningEffort, setReasoningEffort] = useState('')
  const [byokProvider, setByokProvider] = useState('')
  const [byokModel, setByokModel] = useState('')
  const [tokenInput, setTokenInput] = useState('')
  const [hasSecret, setHasSecret] = useState(false)

  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getAgentSettings(), getAgentOptions()])
      .then(([s, o]) => {
        if (cancelled) return
        setLoad({ kind: 'ready', settings: s, options: o })
        setAgent(s.settings.default_agent)
        setQoderMode(s.settings.qoder_mode)
        setQoderModel(s.settings.qoder_model ?? '')
        setReasoningEffort(s.settings.reasoning_effort ?? '')
        setByokProvider(s.settings.byok_provider ?? '')
        setByokModel(s.settings.byok_model ?? '')
        setHasSecret(s.byok.has_secret)
      })
      .catch((err) => { if (!cancelled) setLoad({ kind: 'error', message: String(err) }) })
    return () => { cancelled = true }
  }, [])

  // 当前服务商的模型列表（动态）
  const providerModels = useMemo(() => {
    if (load.kind !== 'ready') return []
    const provider = load.options.byok_providers.find((p) => p.key === byokProvider)
    if (!provider) return []
    return provider.types.flatMap((t) => t.models)
  }, [load, byokProvider])

  const save = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await saveAgentSettings({
        default_agent: agent,
        qoder_mode: qoderMode,
        qoder_model: qoderModel || null,
        reasoning_effort: reasoningEffort || null,
        byok_provider: byokProvider || null,
        byok_model: byokModel || null,
      })
      setMessage({ kind: 'ok', text: '设置已保存' })
    } catch (err) {
      setMessage({ kind: 'error', text: `保存失败：${String(err)}` })
    } finally {
      setSaving(false)
    }
  }

  const saveToken = async () => {
    setMessage(null)
    if (!tokenInput.trim()) {
      setMessage({ kind: 'error', text: '请输入 API Key / Token' })
      return
    }
    try {
      const r = await saveByokSecret(tokenInput.trim())
      setHasSecret(r.has_secret)
      setTokenInput('')
      setMessage({ kind: 'ok', text: 'Token 已保存到系统安全凭据存储' })
    } catch (err) {
      setMessage({ kind: 'error', text: `保存失败：${String(err)}` })
    }
  }

  const removeToken = async () => {
    setMessage(null)
    try {
      const r = await deleteByokSecret()
      setHasSecret(r.has_secret)
      setMessage({ kind: 'ok', text: 'Token 已删除' })
    } catch (err) {
      setMessage({ kind: 'error', text: `删除失败：${String(err)}` })
    }
  }

  const test = async () => {
    setTesting(true)
    setTestResult(null)
    setMessage(null)
    try {
      const r = await testAgentConnection({
        agent,
        qoder_mode: qoderMode,
        qoder_model: qoderModel || null,
        reasoning_effort: reasoningEffort || null,
        byok_provider: byokProvider || null,
        byok_model: byokModel || null,
      })
      setTestResult(r)
    } catch (err) {
      setMessage({ kind: 'error', text: `测试失败：${String(err)}` })
    } finally {
      setTesting(false)
    }
  }

  if (load.kind === 'loading') return <section><h2>设置</h2><p>正在加载…</p></section>
  if (load.kind === 'error') return <section><h2>设置</h2><p>加载失败：{load.message}</p></section>

  const { settings: readySettings, options } = load
  const agents = readySettings.agents
  const selectedAgent = agents.find((a) => a.id === agent)

  const agentRadio = (id: string) => (
    <label key={id} style={{ marginRight: '1rem', cursor: 'pointer' }}>
      <input
        type="radio"
        name="agent"
        value={id}
        checked={agent === id}
        onChange={() => { setAgent(id); setMessage(null) }}
      />
      {AGENT_LABELS[id] ?? id}
    </label>
  )

  const statusLine = (a: typeof selectedAgent) => {
    if (!a) return null
    if (!a.available) return <p style={{ color: '#b00' }}>状态：不可用（{a.error ?? '未知错误'}）</p>
    const caps = a.capabilities
    return (
      <p style={{ color: '#080' }}>
        状态：可用
        {caps && ` · 运行 ${caps.run ? '✓' : '✗'} · 取消 ${caps.cancel ? '✓' : '✗'} · 模型 ${caps.model_selection}`}
      </p>
    )
  }

  const select = (value: string, onChange: (v: string) => void, options_: Array<{ value: string; label: string }>, placeholder: string) => (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ marginRight: '0.75rem' }}>
      <option value="">{placeholder}</option>
      {options_.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )

  return (
    <section>
      <h2>设置</h2>

      <h3 style={{ marginBottom: '0.5rem' }}>Agent</h3>
      <div>{['qoder', 'deepseek_harness'].map(agentRadio)}</div>

      {selectedAgent && agent === 'deepseek_harness' && (
        <div style={{ margin: '0.75rem 0' }}>
          {statusLine(selectedAgent)}
          <p style={{ color: '#666', fontSize: '0.9rem' }}>模型由 Harness profile 管理（headless profile）。</p>
        </div>
      )}

      {agent === 'qoder' && (
        <>
          {statusLine(selectedAgent)}

          <h3 style={{ margin: '1rem 0 0.5rem' }}>模型来源</h3>
          <div>
            <label style={{ marginRight: '1rem', cursor: 'pointer' }}>
              <input type="radio" name="qoder_mode" value="qoder_native" checked={qoderMode === 'qoder_native'}
                onChange={() => { setQoderMode('qoder_native'); setMessage(null) }} />
              Qoder 自带
            </label>
            <label style={{ cursor: 'pointer' }}>
              <input type="radio" name="qoder_mode" value="qoder_byok" checked={qoderMode === 'qoder_byok'}
                onChange={() => { setQoderMode('qoder_byok'); setMessage(null) }} />
              我的 Token Plan / API
            </label>
          </div>

          {qoderMode === 'qoder_native' && (
            <div style={{ margin: '0.75rem 0' }}>
              <div style={{ marginBottom: '0.5rem' }}>
                {select(
                  qoderModel,
                  setQoderModel,
                  options.qoder_models.map((m) => ({ value: m, label: m })),
                  '选择模型（动态读取）',
                )}
                {options.qoder_models_error && (
                  <span style={{ color: '#b00', fontSize: '0.85rem' }}>模型列表加载失败：{options.qoder_models_error}</span>
                )}
              </div>
            </div>
          )}

          {qoderMode === 'qoder_byok' && (
            <div style={{ margin: '0.75rem 0' }}>
              <div style={{ marginBottom: '0.5rem' }}>
                {select(
                  byokProvider,
                  (v) => { setByokProvider(v); setByokModel('') },
                  options.byok_providers.map((p) => ({ value: p.key ?? '', label: p.display_name ?? p.key ?? '' })),
                  '选择服务商（动态读取）',
                )}
                {options.byok_error && (
                  <span style={{ color: '#b00', fontSize: '0.85rem' }}>服务商列表加载失败：{options.byok_error}</span>
                )}
              </div>
              {byokProvider && (
                <div style={{ marginBottom: '0.5rem' }}>
                  {select(
                    byokModel,
                    setByokModel,
                    providerModels.map((m) => ({ value: m.key ?? '', label: m.display_name ?? m.key ?? '' })),
                    '选择模型（根据服务商动态读取）',
                  )}
                </div>
              )}
              <div style={{ marginBottom: '0.5rem' }}>
                {hasSecret ? (
                  <span>
                    API Key / Token：<strong>已保存</strong>（不明文回显）
                    <button onClick={removeToken} style={{ marginLeft: '0.75rem', cursor: 'pointer' }}>删除 Token</button>
                  </span>
                ) : (
                  <span>
                    <input
                      type="password"
                      placeholder="API Key / Token"
                      value={tokenInput}
                      onChange={(e) => setTokenInput(e.target.value)}
                      style={{ width: '20rem', marginRight: '0.5rem' }}
                    />
                    <button onClick={saveToken} style={{ cursor: 'pointer' }}>保存 Token</button>
                  </span>
                )}
              </div>
            </div>
          )}

          <div style={{ marginBottom: '0.5rem' }}>
            思考强度：
            {select(
              reasoningEffort,
              setReasoningEffort,
              options.reasoning_effort_options.map((e) => ({ value: e, label: e })),
              '默认',
            )}
          </div>
        </>
      )}

      <div style={{ marginTop: '1rem' }}>
        <button onClick={save} disabled={saving} style={{ cursor: 'pointer', marginRight: '0.75rem' }}>
          {saving ? '保存中…' : '保存'}
        </button>
        <button onClick={test} disabled={testing} style={{ cursor: 'pointer' }}>
          {testing ? '测试中…' : '测试连接'}
        </button>
      </div>

      {message && (
        <p style={{ marginTop: '0.75rem', color: message.kind === 'ok' ? '#080' : '#b00' }}>{message.text}</p>
      )}
      {testResult && (
        <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', border: '1px solid #ccc', borderRadius: '4px' }}>
          <p style={{ color: testResult.status === 'ok' ? '#080' : testResult.status === 'not_configured' ? '#b70' : '#b00' }}>
            测试结果：{testResult.status === 'ok' ? '连接正常' : testResult.status === 'not_configured' ? '未配置' : '连接失败'}
          </p>
          <p style={{ margin: 0 }}>{testResult.message}</p>
          {testResult.output && <p style={{ margin: '0.25rem 0 0', color: '#666', fontSize: '0.85rem' }}>{testResult.output}</p>}
        </div>
      )}
    </section>
  )
}
