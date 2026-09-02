import { useCallback, useEffect, useState } from 'react'
import { getProjectPresentation, type ProjectPresentation } from '../../bridge/client'

/** Read-only projection of non-semantic project display assets. */
export function useProjectPresentation(projectId: string | null) {
  const [presentation, setPresentation] = useState<ProjectPresentation | null>(null)
  const reload = useCallback(async () => {
    if (!projectId) { setPresentation(null); return }
    const value = await getProjectPresentation(projectId)
    if (value.project_id === projectId) setPresentation(value)
  }, [projectId])
  useEffect(() => { void reload().catch(() => setPresentation(null)) }, [reload])
  useEffect(() => {
    const onMutated = () => { void reload().catch(() => {}) }
    window.addEventListener('gowrite-presentation-mutated', onMutated)
    return () => window.removeEventListener('gowrite-presentation-mutated', onMutated)
  }, [reload])
  return { presentation, reload }
}
