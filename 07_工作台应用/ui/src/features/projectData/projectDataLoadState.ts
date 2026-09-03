export type ProjectDataLoadMode = 'initial' | 'refresh'

/** Existing same-project data stays mounted during reload; other cases truly load. */
export function projectDataLoadMode(currentProjectId: string | null, requestedProjectId: string): ProjectDataLoadMode {
  return currentProjectId === requestedProjectId ? 'refresh' : 'initial'
}

/** A late or cross-project result must never replace the current project. */
export function acceptsProjectDataResponse(
  activeProjectId: string | null,
  requestedProjectId: string,
  responseProjectId: string,
): boolean {
  return activeProjectId === requestedProjectId && responseProjectId === requestedProjectId
}
