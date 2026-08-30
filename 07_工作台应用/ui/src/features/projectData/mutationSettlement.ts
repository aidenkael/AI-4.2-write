import type { AuthorEditResult } from '../../bridge/client'

export interface SettlementFollowUp {
  requestId: string
  changeId: string
  message: string | null
}

/** Backend has already started the unified request; UI only follows and refreshes. */
export function settlementFollowUp(result: unknown): SettlementFollowUp | null {
  if (!result || typeof result !== 'object') return null
  const value = result as AuthorEditResult
  const request = value.settlement_request
  if (
    !value.change?.requires_semantic
    || !request?.request_started
    || typeof request.request_id !== 'string'
    || !request.request_id
  ) return null
  return {
    requestId: request.request_id,
    changeId: value.change.change_id,
    message: request.message ?? null,
  }
}

export function isCurrentProjectResult(expectedProjectId: string, currentProjectId: string | null): boolean {
  return expectedProjectId === currentProjectId
}
