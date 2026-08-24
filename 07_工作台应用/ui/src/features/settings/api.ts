import {
  deleteByokSecret,
  getAgentSettings,
  saveAgentSettings,
  saveByokSecret,
  testAgentConnection,
  type AgentSettingsData,
  type ConnectionTestResult,
} from '../../bridge/client'
import type { SettingsDraft } from './types'

export interface SettingsApi {
  load(): Promise<AgentSettingsData>
  save(draft: SettingsDraft): Promise<AgentSettingsData['settings']>
  test(agent: string, profileId: string | null, model: string | null, effort: string | null): Promise<ConnectionTestResult>
  saveSecret(token: string): Promise<{ secret_id: string; has_secret: boolean }>
  deleteSecret(): Promise<{ secret_id: string | null; has_secret: boolean }>
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
  saveSecret: saveByokSecret,
  deleteSecret: deleteByokSecret,
}
