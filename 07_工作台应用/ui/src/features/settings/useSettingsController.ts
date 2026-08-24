import { useCallback, useEffect, useMemo, useState } from 'react'
import { BridgeError, type AgentEnvironment, type AgentSettingsData, type ExecutionProfile } from '../../bridge/client'
import { settingsApi, type SettingsApi } from './api'
import type { ConnectionState, SettingsDraft, SettingsNotice } from './types'

const toDraft = (data: AgentSettingsData): SettingsDraft => ({
  default_execution_mode: data.settings.default_execution_mode,
  interactive_agent: data.settings.interactive_agent,
  direct_agent: data.settings.direct_agent,
  direct_profile_id: data.settings.direct_profile_id,
  direct_model: data.settings.direct_model,
  reasoning_effort: data.settings.reasoning_effort,
})

const friendlyError = (error: unknown) => {
  const message = error instanceof Error ? error.message : ''
  if (/pywebview|BRIDGE_TIMEOUT|bridge\s*就绪超时/i.test(message)) {
    return '未连接 Go Write 桌面后台，请从桌面应用打开设置后重试。'
  }
  if (error instanceof BridgeError && error.code === 'BRIDGE_INTERNAL') {
    return '设置服务暂时不可用，请稍后重试。'
  }
  return message
    ? message.replace(/^\[[^\]]+\]\s*/, '')
    : '设置服务暂时不可用，请从 Go Write 桌面应用重试。'
}

export function useSettingsController(api: SettingsApi = settingsApi) {
  const [data, setData] = useState<AgentSettingsData | null>(null)
  const [draft, setDraft] = useState<SettingsDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [notice, setNotice] = useState<SettingsNotice | null>(null)
  const [connection, setConnection] = useState<ConnectionState>(null)

  const load = useCallback(async (resetDraft = false) => {
    setLoading(true)
    setNotice(null)
    try {
      const next = await api.load()
      setData(next)
      setDraft((current) => resetDraft || !current ? toDraft(next) : current)
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { void load(true) }, [load])

  const update = useCallback(<K extends keyof SettingsDraft,>(key: K, value: SettingsDraft[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current)
    setConnection(null)
  }, [])

  const agents = data?.agents ?? []
  const interactiveAgent = useMemo(
    () => agents.find((agent) => agent.agent_id === draft?.interactive_agent) ?? null,
    [agents, draft?.interactive_agent],
  )
  const directAgent = useMemo(
    () => agents.find((agent) => agent.agent_id === draft?.direct_agent) ?? null,
    [agents, draft?.direct_agent],
  )
  const directProfile = useMemo<ExecutionProfile | null>(
    () => directAgent?.direct.execution_profiles.find((profile) => profile.id === draft?.direct_profile_id) ?? null,
    [directAgent, draft?.direct_profile_id],
  )
  const directValid = Boolean(
    directProfile?.available && (
      directProfile.model_selection !== 'selectable' ||
      directProfile.models.some((model) => model.id === draft?.direct_model && model.selectable)
    ),
  )
  const interactiveValid = Boolean(interactiveAgent?.interactive.command_ready && interactiveAgent.interactive.bridge_ready)
  const canSave = Boolean(draft && (
    draft.default_execution_mode === 'direct' ? directValid : interactiveValid
  ))

  const save = useCallback(async () => {
    if (!draft || !canSave) return
    setSaving(true)
    setNotice(null)
    try {
      await api.save(draft)
      await load(true)
      setNotice({ kind: 'success', message: '执行设置已安全保存' })
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setSaving(false)
    }
  }, [api, canSave, draft, load])

  const test = useCallback(async () => {
    if (!draft || !directValid) return
    setTesting(true)
    setConnection(null)
    try {
      setConnection(await api.test(
        draft.direct_agent,
        draft.direct_profile_id,
        draft.direct_model,
        draft.reasoning_effort,
      ))
    } catch (error) {
      setConnection({ agent: draft.direct_agent, status: 'failed', message: friendlyError(error) })
    } finally {
      setTesting(false)
    }
  }, [api, directValid, draft])

  const saveSecret = useCallback(async (token: string) => {
    if (!token.trim()) return
    setSaving(true)
    try {
      await api.saveSecret(token.trim())
      await load(false)
      setNotice({ kind: 'success', message: '凭据已保存到系统安全存储' })
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setSaving(false)
    }
  }, [api, load])

  const deleteSecret = useCallback(async () => {
    setSaving(true)
    try {
      await api.deleteSecret()
      await load(false)
      setNotice({ kind: 'success', message: '已删除安全凭据' })
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setSaving(false)
    }
  }, [api, load])

  return {
    data, draft, agents, interactiveAgent, directAgent, directProfile,
    loading, saving, testing, notice, connection, directValid, interactiveValid, canSave,
    update, refresh: () => load(false), save, test, saveSecret, deleteSecret,
  }
}

export type SettingsController = ReturnType<typeof useSettingsController>
export type { AgentEnvironment }
