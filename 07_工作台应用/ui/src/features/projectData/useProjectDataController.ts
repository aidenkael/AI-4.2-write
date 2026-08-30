/**
 * 作品地基 / 故事地图统一快照消费者控制器（共用）。
 *
 * 约束：只读 getProjectData；零写回、零模型；换项目丢弃过期结果。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createFoundationRecord,
  createRelationship,
  getChangeSettlementRequest,
  getProjectData,
  prepareChangeSettlement,
  restoreFoundationRecord,
  restoreRelationship,
  retireFoundationRecord,
  retireRelationship,
  setLengthPlan,
  setStoryBibleProfile,
  updateFoundationRecord,
  updateRelationship,
  type AuthorEditResult,
  type ProjectData,
} from '../../bridge/client'
import { isCurrentProjectResult, settlementFollowUp } from './mutationSettlement'

export interface ProjectDataController {
  data: ProjectData | null
  loading: boolean
  error: string | null
  saving: boolean
  syncing: boolean
  syncMessage: string | null
  reload(): Promise<void>
  createFoundation(input: { category: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  updateFoundation(input: { ref: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  retireFoundation(ref: string): Promise<boolean>
  restoreFoundation(ref: string): Promise<boolean>
  createRelationship(input: { source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  updateRelationship(input: { ref: string; source_ref: string; target_ref: string; label: string; material_state: 'current' | 'future'; data: Record<string, unknown> }): Promise<boolean>
  retireRelationship(ref: string): Promise<boolean>
  restoreRelationship(ref: string): Promise<boolean>
  saveLengthPlan(input: { total_target_words: number | null; stages: Array<Record<string, unknown>>; chapter_targets: Array<Record<string, unknown>> }): Promise<boolean>
  saveProfile(input: { genre_tags: string[]; narrative_mode: string | null; active_modules: string[]; field_config: Record<string, unknown> }): Promise<boolean>
  /** 显式重试一条待同步/失败的语义变更（配置日常 AI 之后的恢复入口）。 */
  retrySettlement(): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useProjectDataController(projectId: string | null): ProjectDataController {
  const [data, setData] = useState<ProjectData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)
  const projectRef = useRef<string | null>(projectId)
  const followedRequestsRef = useRef(new Set<string>())
  projectRef.current = projectId

  const load = useCallback(async (pid: string) => {
    setLoading(true)
    setError(null)
    try {
      const next = await getProjectData(pid)
      if (projectRef.current !== pid) return
      if (next.project_id !== pid) throw new Error('返回的作品数据与当前作品不一致，已拒绝。')
      setData(next)
    } catch (e) {
      if (projectRef.current !== pid) return
      setError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setLoading(false)
    }
  }, [])

  useEffect(() => {
    setSyncing(false)
    setSyncMessage(null)
    followedRequestsRef.current.clear()
    setData(null)
    if (!projectId) {
      setLoading(false)
      setError(null)
      return
    }
    void load(projectId)
  }, [projectId, load])

  const reload = useCallback(async () => {
    if (projectId) await load(projectId)
  }, [load, projectId])

  const followSettlement = useCallback(async (pid: string, result: AuthorEditResult) => {
    const follow = settlementFollowUp(result)
    if (!follow) return
    if (!isCurrentProjectResult(pid, projectRef.current)) return
    if (followedRequestsRef.current.has(follow.requestId)) return
    followedRequestsRef.current.add(follow.requestId)
    setSyncing(true)
    setSyncMessage(follow.message ?? '正在同步最新作品状态。')
    try {
      let status = await getChangeSettlementRequest(follow.requestId)
      while (isCurrentProjectResult(pid, projectRef.current) && status.status === 'pending') {
        setSyncMessage(status.message ?? follow.message ?? '正在同步最新作品状态。')
        await new Promise((resolve) => window.setTimeout(resolve, 1000))
        status = await getChangeSettlementRequest(follow.requestId)
      }
      if (!isCurrentProjectResult(pid, projectRef.current)) return
      if (status.project_id && status.project_id !== pid) return
      if (status.status === 'failed') throw new Error(status.error || '同步失败，可稍后重试。')
      await load(pid)
      if (!isCurrentProjectResult(pid, projectRef.current)) return
      setSyncMessage(null)
    } catch (e) {
      if (isCurrentProjectResult(pid, projectRef.current)) {
        setError(toMessage(e))
        setSyncMessage('同步失败')
        await load(pid)
      }
    } finally {
      followedRequestsRef.current.delete(follow.requestId)
      if (isCurrentProjectResult(pid, projectRef.current)) setSyncing(false)
    }
  }, [load])

  const refreshQuiet = useCallback(async (pid: string) => {
    try {
      const next = await getProjectData(pid)
      if (projectRef.current !== pid || next.project_id !== pid) return
      setData(next)
    } catch {
      // 静默轮询：保留上一份有效数据，绝不把瞬时错误展示给作者。
    }
  }, [])

  useEffect(() => {
    if (!projectId || !data) return
    if (data.settlement.status === 'synchronized') return
    // Direct AI 结算是轻量后台维护：只轮询只读投影，不进全局任务条，
    // 也不触发加载态闪烁。
    const timer = window.setInterval(() => { void refreshQuiet(projectId) }, 2000)
    return () => window.clearInterval(timer)
  }, [projectId, data, refreshQuiet])

  useEffect(() => {
    if (!projectId || !data) return
    const pending = data.settlement.changes.find((change) => (
      change.status === 'pending'
      && change.requires_semantic
      && change.settlement_started
      && change.settlement_request_id
    ))
    if (!pending?.settlement_request_id) return
    void followSettlement(projectId, {
      change: pending,
      settlement_request: {
        change_id: pending.change_id, requires_semantic: true, status: pending.status,
        complete: false, request_started: true, request_id: pending.settlement_request_id,
      },
    })
  }, [data, followSettlement, projectId])

  const mutate = useCallback(async (action: (pid: string, rev: number) => Promise<AuthorEditResult>) => {
    const pid = projectRef.current
    const rev = data?.project_id === pid ? data.model_rev : null
    if (!pid || rev == null) {
      setError('作品数据尚未加载完成。')
      return false
    }
    setSaving(true)
    setError(null)
    try {
      const result = await action(pid, rev)
      await load(pid)
      void followSettlement(pid, result)
      return true
    } catch (e) {
      if (projectRef.current === pid) setError(toMessage(e))
      return false
    } finally {
      if (projectRef.current === pid) setSaving(false)
    }
  }, [data?.model_rev, data?.project_id, followSettlement, load])

  const createFoundation = useCallback((input: { category: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => createFoundationRecord({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const updateFoundation = useCallback((input: { ref: string; title: string; material_state: 'current' | 'future'; data: Record<string, unknown> }) => (
    mutate((pid, rev) => updateFoundationRecord({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const retireFoundation = useCallback((ref: string) => (
    mutate((pid, rev) => retireFoundationRecord({ project_id: pid, base_model_rev: rev, ref }))
  ), [mutate])

  const restoreFoundation = useCallback((ref: string) => (
    mutate((pid, rev) => restoreFoundationRecord({ project_id: pid, base_model_rev: rev, ref }))
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

  const restoreRelationshipAction = useCallback((ref: string) => (
    mutate((pid, rev) => restoreRelationship({ project_id: pid, base_model_rev: rev, ref }))
  ), [mutate])

  const saveLengthPlan = useCallback((input: { total_target_words: number | null; stages: Array<Record<string, unknown>>; chapter_targets: Array<Record<string, unknown>> }) => (
    mutate((pid, rev) => setLengthPlan({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const saveProfile = useCallback((input: { genre_tags: string[]; narrative_mode: string | null; active_modules: string[]; field_config: Record<string, unknown> }) => (
    mutate((pid, rev) => setStoryBibleProfile({ project_id: pid, base_model_rev: rev, ...input }))
  ), [mutate])

  const retrySettlement = useCallback(async () => {
    const pid = projectRef.current
    const target = data?.settlement.changes.find((change) => (
      change.requires_semantic && (change.status === 'pending' || change.status === 'failed')
    ))
    if (!pid || !target) return
    try {
      await prepareChangeSettlement({ project_id: pid, change_id: target.change_id })
    } catch (e) {
      if (projectRef.current === pid) setError(toMessage(e))
    }
    if (projectRef.current === pid) await load(pid)
  }, [data?.settlement.changes, load])

  return {
    data, loading, error, saving, syncing, syncMessage, reload,
    createFoundation, updateFoundation, retireFoundation, restoreFoundation,
    createRelationship: createRelationshipAction,
    updateRelationship: updateRelationshipAction,
    retireRelationship: retireRelationshipAction,
    restoreRelationship: restoreRelationshipAction,
    saveLengthPlan, saveProfile, retrySettlement,
  }
}
