import { Cloud } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getSemanticAiSettings, saveSemanticAiSettings, type SemanticAiSettings } from '../../../bridge/client'

/**
 * 日常 AI：作者明确更新作品状态时的 Direct AI 语义整理配置面。
 * 与 Agent 执行设置完全独立；API Key 只写入系统凭据存储，绝不回传明文。
 */
export function SemanticAiSettingsSection() {
  const [saved, setSaved] = useState<SemanticAiSettings | null>(null)
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    let active = true
    getSemanticAiSettings()
      .then((settings) => {
        if (!active) return
        setSaved(settings)
        setBaseUrl(settings.semantic_ai_base_url)
        setModel(settings.semantic_ai_model)
      })
      .catch((error) => {
        if (active) setNotice({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
      })
    return () => { active = false }
  }, [])

  const save = async () => {
    setSaving(true)
    setNotice(null)
    try {
      const payload: { semantic_ai_base_url: string; semantic_ai_model: string; api_key?: string } = {
        semantic_ai_base_url: baseUrl.trim(),
        semantic_ai_model: model.trim(),
      }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      const result = await saveSemanticAiSettings(payload)
      setSaved(result.settings)
      setApiKey('')
      setNotice({ kind: 'success', message: '日常 AI 设置已保存。' })
    } catch (error) {
      setNotice({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="semantic-ai-settings">
      <div className="api-summary">
        <Cloud />
        <div>
          <h3>日常 AI</h3>
          <p>仅在你明确执行「更新作品状态」时，用于有界整理人物、关系、事件等语义后果。保存正文、地基或规划不会自动调用它；它与创作任务的 Agent 执行完全独立。</p>
        </div>
      </div>
      <label>API 地址
        <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" />
      </label>
      <label>模型
        <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="OpenAI 兼容模型名" />
      </label>
      <label>API Key
        <input
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder={saved?.has_api_key ? '已安全保存（留空则保持不变）' : '输入后只保存到系统凭据存储'}
        />
      </label>
      {notice ? <div className={`settings-notice ${notice.kind}`}>{notice.message}</div> : null}
      <div className="settings-savebar">
        <span className="muted-note">
          {saved ? (saved.configured ? '当前：已配置完成' : '当前：尚未配置完成（缺少地址 / 模型 / Key 之一）') : '正在读取当前配置…'}
        </span>
        <button className="primary" disabled={saving || !baseUrl.trim() || !model.trim()} onClick={() => void save()}>保存</button>
      </div>
    </div>
  )
}
