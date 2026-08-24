import type { AgentSettings, ConnectionTestResult } from '../../bridge/client'

export type SettingsSection = 'AI 服务 / API' | 'Agent' | '执行配置' | '项目与数据' | '插图与视觉' | '高级设置'
export type SettingsDraft = Pick<AgentSettings,
  'default_execution_mode' | 'interactive_agent' | 'direct_agent' | 'direct_model'
>

export interface SettingsNotice {
  kind: 'success' | 'error' | 'info'
  message: string
}

export type ConnectionState = ConnectionTestResult | null
