/**
 * 素材工作流真实消费者控制器（App 级协调器消费者）。
 *
 * 工作流：本地文件导入 → MaterialIntake 收件箱 → scan → 确定性事实优先、
 * 无法定论时一次 Agent 分类 → 作者确认 → 事务入库 → 显式提纯（SourcePrepare）
 * → 显式蒸馏（BookDistill）→ FINALIZED BKP → 可用于写作。
 *
 * 生命周期归属（根不变量）：
 * - material_classify / material_distill 的异步状态属于 App 级协调器；
 *   离开素材页任务继续、结果保留，返回后页面显式消费；
 * - MaterialIntake apply 与 SourcePrepare 是确定性机械操作，留在本控制器；
 * - 页面加载只读（listMaterials）+ 一次确定性收件箱扫描（零模型）；
 *   绝不隐式调用模型 / 提纯 / 蒸馏。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  applyMaterialIntake,
  getMaterialDetail,
  importMaterialFiles,
  listMaterials,
  pickMaterialFiles,
  prepareMaterial,
  refreshMaterials,
  scanMaterialInbox,
  type ClassifyMaterialResult,
  type ImportMaterialResult,
  type MaterialDetail,
  type MaterialInboxFile,
  type MaterialIntakeResult,
  type MaterialItem,
} from '../../bridge/client'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'

export interface MaterialsController {
  materials: MaterialItem[]
  loading: boolean
  error: string | null
  refreshing: boolean
  inbox: MaterialInboxFile[]
  inboxLoading: boolean
  inboxError: string | null
  applying: boolean
  classifyState: 'idle' | 'running' | 'waiting_gowrite' | 'done' | 'failed'
  classifyResult: ClassifyMaterialResult | null
  importResult: ImportMaterialResult | null
  importing: boolean
  busyAssetId: string | null
  busyKind: 'prepare' | 'distill' | null
  detail: MaterialDetail | null
  detailLoading: boolean
  reload(): Promise<void>
  refresh(): Promise<boolean>
  scanInbox(): Promise<void>
  pickAndImport(): Promise<ImportMaterialResult | null>
  classify(): Promise<void>
  cancelClassify(): Promise<void>
  confirmApply(): Promise<boolean>
  selectDetail(assetId: string): Promise<void>
  runPrepare(assetId: string): Promise<boolean>
  runDistill(assetId: string): Promise<boolean>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useMaterialsController(options?: { notify?: (message: string) => void }): MaterialsController {
  const notify = options?.notify
  const { task, start, cancel: cancelTask, consume } = useAuthorTask()
  const [materials, setMaterials] = useState<MaterialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [inbox, setInbox] = useState<MaterialInboxFile[]>([])
  const [inboxLoading, setInboxLoading] = useState(false)
  const [inboxError, setInboxError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportMaterialResult | null>(null)
  const [classifyState, setClassifyState] = useState<MaterialsController['classifyState']>('idle')
  const [classifyResult, setClassifyResult] = useState<ClassifyMaterialResult | null>(null)
  const [busyAssetId, setBusyAssetId] = useState<string | null>(null)
  const [busyKind, setBusyKind] = useState<MaterialsController['busyKind']>(null)
  const [detail, setDetail] = useState<MaterialDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const sourcePrepareAssetRef = useRef<string | null>(null)

  // ---------------- 只读数据：挂载加载素材目录 + 一次确定性收件箱扫描 ----------------

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await listMaterials()
      setMaterials(items)
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const scanInbox = useCallback(async () => {
    setInboxLoading(true)
    setInboxError(null)
    try {
      const result = await scanMaterialInbox()
      setInbox(result.files)
    } catch (e) {
      setInboxError(toMessage(e))
    } finally {
      setInboxLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
    void scanInbox() // 页面打开在「待处理」：确定性扫描一次，计数/列表真实
  }, [reload, scanInbox])

  // ---------------- 详情 / 提纯（显式同步）/ 蒸馏（协调器任务） ----------------

  const selectDetail = useCallback(async (assetId: string) => {
    setDetailLoading(true)
    setError(null)
    try {
      const d = await getMaterialDetail(assetId)
      setDetail(d)
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  // ---------------- 协调器任务 → 本页投影（classify / distill） ----------------

  const classifyTask = task?.kind === 'material_classify' ? task : null
  const distillTask = task?.kind === 'material_distill' ? task : null

  // classify：运行中/等待 → 状态映射；候选/失败 → 显式消费
  useEffect(() => {
    if (!classifyTask) return
    if (classifyTask.status === 'running' || classifyTask.status === 'pending') {
      setClassifyState('running')
      return
    }
    if (classifyTask.status === 'waiting_author') {
      setClassifyState('waiting_gowrite')
      return
    }
    if (classifyTask.status === 'candidate' && classifyTask.result) {
      const result = classifyTask.result as ClassifyMaterialResult
      setClassifyState('done')
      setClassifyResult(result)
      consume()
      return
    }
    if (classifyTask.status === 'failed') {
      setClassifyState('failed')
      setError(classifyTask.error ?? '分类失败，请重试。')
      consume()
      return
    }
  }, [classifyTask, consume])

  // distill：busy 指示（asset_id 来自任务 meta）+ 完成/失败显式消费
  useEffect(() => {
    if (!distillTask) return
    const assetId = typeof distillTask.meta?.asset_id === 'string' ? distillTask.meta.asset_id : null
    if (distillTask.status === 'running' || distillTask.status === 'pending' || distillTask.status === 'waiting_author') {
      setBusyAssetId(assetId)
      setBusyKind('distill')
      return
    }
    if (distillTask.status === 'candidate' && distillTask.result) {
      const result = distillTask.result as { message?: string }
      notify?.(result.message ?? '蒸馏完成')
      void reload()
      if (detail?.id && detail.id === assetId) void selectDetail(detail.id)
      setBusyAssetId(null)
      setBusyKind(null)
      consume()
      return
    }
    if (distillTask.status === 'failed') {
      setBusyAssetId(null)
      setBusyKind(null)
      setError(distillTask.error ?? '蒸馏失败，请重试。')
      consume()
      return
    }
  }, [distillTask, consume, detail?.id, notify, reload, selectDetail])

  // ---------------- 导入 / 分类 ----------------

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setError(null)
    try {
      const result = await refreshMaterials()
      await reload()
      notify?.(result.message || '素材状态已刷新')
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setRefreshing(false)
    }
  }, [notify, reload])

  const pickAndImport = useCallback(async () => {
    setImporting(true)
    setError(null)
    try {
      const picked = await pickMaterialFiles()
      if (!picked.supported) {
        setError(picked.message || '当前环境不支持文件选择。')
        return null
      }
      if (!picked.paths.length) return null
      const result = await importMaterialFiles(picked.paths.map((path) => ({ path })))
      setImportResult(result)
      notify?.(result.message)
      await scanInbox()
      return result
    } catch (e) {
      setError(toMessage(e))
      return null
    } finally {
      setImporting(false)
    }
  }, [notify, scanInbox])

  const classify = useCallback(async () => {
    setClassifyState('running')
    setError(null)
    const busy = await start({ kind: 'material_classify' })
    if (busy) {
      setClassifyState('failed')
      setError(busy)
    }
  }, [start])

  const cancelClassify = useCallback(async () => {
    setClassifyState('idle')
    setClassifyResult(null)
    await cancelTask()
  }, [cancelTask])

  // ---------------- 入库确认（MaterialIntake 机械事务，非 AI 任务） ----------------

  const confirmApply = useCallback(async () => {
    const plan = classifyResult?.plan
    if (!plan || !plan.items?.length) {
      setError('没有可执行的入库计划。')
      return false
    }
    setApplying(true)
    setError(null)
    try {
      const result: MaterialIntakeResult = await applyMaterialIntake(plan)
      await reload()
      await scanInbox()
      if (result.git_warning) notify?.(result.git_warning)
      else notify?.(result.message || '素材入库已完成')
      setClassifyState('idle')
      setClassifyResult(null)
      setImportResult(null)
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setApplying(false)
    }
  }, [classifyResult, notify, reload, scanInbox])

  // ---------------- 详情 / 提纯（显式同步）/ 蒸馏（协调器任务） ----------------

  const runPrepare = useCallback(async (assetId: string) => {
    sourcePrepareAssetRef.current = assetId
    setBusyAssetId(assetId)
    setBusyKind('prepare')
    setError(null)
    try {
      const result = await prepareMaterial(assetId)
      notify?.(result.message)
      await reload()
      if (detail?.id === assetId) await selectDetail(assetId)
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      sourcePrepareAssetRef.current = null
      setBusyAssetId(null)
      setBusyKind(null)
    }
  }, [detail?.id, notify, reload, selectDetail])

  const runDistill = useCallback(async (assetId: string) => {
    setError(null)
    setBusyAssetId(assetId)
    setBusyKind('distill')
    const busy = await start({ kind: 'material_distill', asset_id: assetId })
    if (busy) {
      setBusyAssetId(null)
      setBusyKind(null)
      setError(busy)
      return false
    }
    return true
  }, [start])

  return {
    materials, loading, error, refreshing,
    inbox, inboxLoading, inboxError, applying,
    classifyState, classifyResult, importResult, importing,
    busyAssetId, busyKind, detail, detailLoading,
    reload, refresh, scanInbox, pickAndImport, classify, cancelClassify, confirmApply,
    selectDetail, runPrepare, runDistill,
  }
}
