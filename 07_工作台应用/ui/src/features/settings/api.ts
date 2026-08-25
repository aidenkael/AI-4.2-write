import {
  discoverAgents,
  getAgentSettings,
  installOrRepairInteractiveCommand,
  saveAgentSettings,
  testAgentConnection,
  type AgentEnvironment,
  type AgentSettingsData,
  type ConnectionTestResult,
  type InteractiveRepairResult,
} from '../../bridge/client'
import type { SettingsDraft } from './types'

export interface DiscoverySnapshot {
  agents: AgentEnvironment[]
  discovery: AgentSettingsData['discovery']
}

export interface SettingsApi {
  /** 打开设置页：已保存设置 + last-known 发现快照（后端缓存，不重跑发现）。 */
  load(): Promise<AgentSettingsData>
  /** 显式“重新检测”：强制刷新本机 Agent/模型目录。 */
  discover(): Promise<DiscoverySnapshot>
  save(draft: SettingsDraft): Promise<AgentSettingsData['settings']>
  test(agent: string, model: string | null, customModel: string | null): Promise<ConnectionTestResult>
  repairInteractive(agent: string): Promise<InteractiveRepairResult>
}

export const settingsApi: SettingsApi = {
  load: getAgentSettings,
  async discover() {
    return discoverAgents()
  },
  async save(draft) {
    const result = await saveAgentSettings(draft)
    return result.settings
  },
  test(agent, model, customModel) {
    return testAgentConnection({ agent, model, custom_model: customModel })
  },
  repairInteractive: installOrRepairInteractiveCommand,
}
