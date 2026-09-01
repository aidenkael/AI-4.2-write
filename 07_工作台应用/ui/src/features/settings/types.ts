import type { AgentSettings, ConnectionTestResult } from '../../bridge/client'

export type SettingsSection = 'AI 与执行' | '界面与通知' | '执行记录'
export type SettingsDraft = Pick<AgentSettings,
  'default_execution_mode' | 'interactive_agent' | 'direct_agent' | 'direct_model' | 'direct_custom_model'
>

export interface SettingsNotice {
  kind: 'success' | 'error' | 'info'
  message: string
}

export type ConnectionState = ConnectionTestResult | null
