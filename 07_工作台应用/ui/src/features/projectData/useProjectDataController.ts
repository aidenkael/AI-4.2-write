/**
 * 作品地基 / 故事地图统一快照消费者控制器（共用）。
 *
 * 约束：只读 getProjectData；零写回、零模型；换项目丢弃过期结果。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createFoundationRecord,
  createRelationship,
  getProjectData,
  retireFoundationRecord,
  retireRelationship,
  setLengthPlan,
  updateFoundationRecord,
  updateRelationship,
  type ProjectData,
} from '../../bridge/client'

export interface ProjectDataController {
  data: ProjectData | null
  loading: boolean
  error: string | null
  saving: boolean
  reload(): Promise<void>
  createFoundation(input: { category: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  updateFoundation(input: { ref: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  retireFoundation(ref: string): Promise<boolean>
  createRelationship(input: { source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  updateRelationship(input: { ref: string; source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  retireRelationship(ref: string): Promise<boolean>
  saveLengthPlan(input: { total_target_words: number | null; stages: Array<Record<string, unknown>>; chapter_targets: Array<Record<string, unknown>> }): Promise<boolean>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useProjectDataController(projectId: string | null): ProjectDataController {
  const [data, setData] = useState<ProjectData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId

  const load = useCallback(async (pid: string) => {
    setLoading(true)
    setError(null)
    try {
      const next = await getProjectData(pid)
      if (projectRef.current !== pid) return
      setData(next)
    } catch (e) {
      if (projectRef.current !== pid) return
      setError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!projectId) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    void load(projectId)
  }, [projectId, load])

  const reload = useCallback(async () => {
    if (projectId) await load(projectId)
  }, [load, projectId])

  const mutate = useCallback(async (action: (pid: string, rev: number) => Promise<unknown>) => {
    const pid = projectRef.current
    const rev = data?.model_rev
    if (!pid || rev == null) {
      setError('作品数据尚未加载完成。')
      return false
    }
    setSaving(true)
    setError(null)
    try {
      await action(pid, rev)
      await load(pid)
      return true
    } catch (e) {
      if (projectRef.current === pid) setError(toMessage(e))
      return false
    } finally {
      if (projectRef.current === pid) setSaving(false)
    }
  }, [data?.model_rev, load])

  const createFoundation = useCallback((input: { category: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => createFoundationRecord({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const updateFoundation = useCallback((input: { ref: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => updateFoundationRecord({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const retireFoundation = useCallback((ref: string) => (
    mutate((pid, rev) => retireFoundationRecord({ project_id: pid, base_model_rev: rev, ref }))
  ), [mutate])

  const createRelationshipAction = useCallback((input: { source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => createRelationship({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const updateRelationshipAction = useCallback((input: { ref: string; source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => updateRelationship({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const retireRelationshipAction = useCallback((ref: string) => (
    mutate((pid, rev) => retireRelationship({ project_id: pid, base_model_rev: rev, ref }))
  ), [mutate])

  const saveLengthPlan = useCallback((input: { total_target_words: number | null; stages: Array<Record<string, unknown>>; chapter_targets: Array<Record<string, unknown>> }) => (
    mutate((pid, rev) => setLengthPlan({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  return {
    data, loading, error, saving, reload,
    createFoundation, updateFoundation, retireFoundation,
    createRelationship: createRelationshipAction,
    updateRelationship: updateRelationshipAction,
    retireRelationship: retireRelationshipAction,
    saveLengthPlan,
  }
}
