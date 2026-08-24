import {
  getAgentSettings,
  installOrRepairInteractiveCommand,
  saveAgentSettings,
  testAgentConnection,
  type AgentSettingsData,
  type ConnectionTestResult,
} from '../../bridge/client'
import type { SettingsDraft } from './types'

export interface SettingsApi {
  load(): Promise<AgentSettingsData>
  save(draft: SettingsDraft): Promise<AgentSettingsData['settings']>
  test(agent: string, profileId: string | null, model: string | null, effort: string | null): Promise<ConnectionTestResult>
  repairInteractive(agent: string): Promise<{ installed_paths: string[]; command_ready: boolean; errors: string[] }>
}

export const settingsApi: SettingsApi = {
  load: getAgentSettings,
  async save(draft) {
    const result = await saveAgentSettings(draft)
    return result.settings
  },
  test(agent, profileId, model, effort) {
    return testAgentConnection({ agent, profile_id: profileId, model, reasoning_effort: effort })
  },
  repairInteractive: installOrRepairInteractiveCommand,
}
