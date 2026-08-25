import { useCallback, useEffect, useMemo, useState } from 'react'
import { BridgeError, type AgentEnvironment, type AgentSettings, type AgentSettingsData } from '../../bridge/client'
import { settingsApi, type SettingsApi } from './api'
import type { ConnectionState, SettingsDraft, SettingsNotice } from './types'

const toDraft = (data: AgentSettingsData): SettingsDraft => ({
  default_execution_mode: data.settings.default_execution_mode,
  interactive_agent: data.settings.interactive_agent,
  direct_agent: data.settings.direct_agent,
  direct_model: data.settings.direct_model,
  direct_custom_model: data.settings.direct_custom_model,
})

const sameDraft = (a: SettingsDraft | null, b: AgentSettings | null): boolean => {
  if (!a || !b) return false
  return (
    a.default_execution_mode === b.default_execution_mode &&
    a.interactive_agent === b.interactive_agent &&
    a.direct_agent === b.direct_agent &&
    a.direct_model === b.direct_model &&
    a.direct_custom_model === b.direct_custom_model
  )
}

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

  // 挂载只读取“已保存设置 + last-known 发现快照”：
  // 不强制重跑发现；只有“重新检测”才触发 discover()。
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

  // 显式“重新检测”：只刷新本机 Agent/模型目录快照，不改已保存配置。
  const refresh = useCallback(async () => {
    setLoading(true)
    setNotice(null)
    try {
      const snapshot = await api.discover()
      setData((current) => current
        ? { ...current, agents: snapshot.agents, discovery: snapshot.discovery }
        : current)
      setNotice({ kind: 'success', message: '已重新检测本机环境；已保存配置未改变。' })
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setLoading(false)
    }
  }, [api])

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
  const directValid = Boolean(
    directAgent?.direct.available && (
      directAgent.direct.models.some((model) => model.id === draft?.direct_model && model.selectable) ||
      directAgent.direct.custom_models.some((model) => model.id === draft?.direct_custom_model && model.selectable)
    ),
  )
  const interactiveValid = Boolean(interactiveAgent?.interactive.command_ready && interactiveAgent.interactive.bridge_ready)
  // 已保存配置 = 与后端持久化值一致；即使当前发现未包含所选模型（本页未重跑检测），
  // 原样保存/展示也应成立，绝不因未检测而作废已保存选择。
  const isSavedConfig = sameDraft(draft, data?.settings ?? null)
  const canSave = Boolean(draft && (
    isSavedConfig || (draft.default_execution_mode === 'direct' ? directValid : interactiveValid)
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
      setConnection(await api.test(draft.direct_agent, draft.direct_model, draft.direct_custom_model))
    } catch (error) {
      setConnection({ agent: draft.direct_agent, status: 'failed', message: friendlyError(error) })
    } finally {
      setTesting(false)
    }
  }, [api, directValid, draft])

  const repairInteractive = useCallback(async () => {
    if (!draft) return
    setSaving(true)
    try {
      const result = await api.repairInteractive(draft.interactive_agent)
      await refresh()
      if (result.status === 'restart_required' || result.restart_required) {
        setNotice({ kind: 'info', message: '命令已安装，但 Qoder Desktop 需要重启或重新加载后才能识别 /gowrite。' })
      } else if (result.status === 'installed' && result.command_ready) {
        setNotice({ kind: 'success', message: '/gowrite 命令已安装/修复，已重新检测并可用' })
      } else {
        setNotice({ kind: 'error', message: result.errors.join('；') || '命令安装失败' })
      }
    } catch (error) {
      setNotice({ kind: 'error', message: friendlyError(error) })
    } finally {
      setSaving(false)
    }
  }, [api, refresh])

  return {
    data, draft, agents, interactiveAgent, directAgent,
    loading, saving, testing, notice, connection, directValid, interactiveValid, canSave, isSavedConfig,
    update, refresh, save, test, repairInteractive,
  }
}

export type SettingsController = ReturnType<typeof useSettingsController>
export type { AgentEnvironment }
