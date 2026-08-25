/**
 * 素材工作流真实消费者控制器。
 *
 * 工作流：本地文件导入 → MaterialIntake 收件箱 → scan → 确定性事实优先、
 * 无法定论时一次 Agent 分类 → 作者确认 → 事务入库 → 显式提纯（SourcePrepare）
 * → 显式蒸馏（BookDistill）→ FINALIZED BKP → 可用于写作（KnowledgeRetrieve 按需调用）。
 *
 * 约束：
 * - 页面加载只读（listMaterials）；绝不调用模型 / SourcePrepare / BookDistill；
 * - 导入、分类、提纯、蒸馏都是作者显式动作；
 * - Agent 只输出决策，绝不移动文件/改台账；入库走 MaterialIntake 事务。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  applyMaterialIntake,
  cancelMaterialClassifyRequest,
  classifyMaterialInbox,
  getBookDistillRequest,
  getMaterialClassifyRequest,
  getMaterialDetail,
  importMaterialFiles,
  listMaterials,
  pickMaterialFiles,
  refreshMaterials,
  runBookDistill,
  runSourcePrepare,
  scanMaterialInbox,
  type BookDistillRequestStatus,
  type ClassifyMaterialResult,
  type ClassifyRequestStatus,
  type ImportMaterialResult,
  type MaterialDetail,
  type MaterialInboxFile,
  type MaterialIntakeResult,
  type MaterialItem,
} from '../../bridge/client'

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
  busyKind: 'source_prepare' | 'book_distill' | null
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

const POLL_INTERVAL_MS = 1500

export function useMaterialsController(options?: { notify?: (message: string) => void }): MaterialsController {
  const notify = options?.notify
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
  const classifyRequestRef = useRef<string | null>(null)
  const distillRequestRef = useRef<string | null>(null)
  const classifyTimerRef = useRef<number | null>(null)
  const distillTimerRef = useRef<number | null>(null)
  const unmountedRef = useRef(false)

  useEffect(() => {
    unmountedRef.current = false
    return () => {
      unmountedRef.current = true
      if (classifyTimerRef.current) window.clearTimeout(classifyTimerRef.current)
      if (distillTimerRef.current) window.clearTimeout(distillTimerRef.current)
    }
  }, [])

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await listMaterials()
      if (unmountedRef.current) return
      setMaterials(items)
    } catch (e) {
      if (!unmountedRef.current) setError(toMessage(e))
    } finally {
      if (!unmountedRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

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

  const scanInbox = useCallback(async () => {
    setInboxLoading(true)
    setInboxError(null)
    try {
      const result = await scanMaterialInbox()
      if (!unmountedRef.current) setInbox(result.files)
    } catch (e) {
      if (!unmountedRef.current) setInboxError(toMessage(e))
    } finally {
      if (!unmountedRef.current) setInboxLoading(false)
    }
  }, [])

  // ---------------- 导入 / 分类 ----------------

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
      if (!unmountedRef.current) {
        setImportResult(result)
        notify?.(result.message)
        await scanInbox()
      }
      return result
    } catch (e) {
      setError(toMessage(e))
      return null
    } finally {
      if (!unmountedRef.current) setImporting(false)
    }
  }, [notify, scanInbox])

  const pollClassify = useCallback(async (requestId: string) => {
    const tick = async () => {
      if (unmountedRef.current) return
      try {
        const res: ClassifyRequestStatus = await getMaterialClassifyRequest(requestId)
        if (unmountedRef.current) return
        if (res.status === 'pending') {
          setClassifyState('waiting_gowrite')
          classifyTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS)
          return
        }
        classifyRequestRef.current = null
        if (res.status === 'completed') {
          setClassifyState('done')
          setClassifyResult({ status: 'ready', plan: res.plan ?? { items: [] }, message: res.message ?? '入库建议已生成' })
          notify?.(res.message ?? '入库建议已生成，请确认后执行。')
        } else {
          setClassifyState('failed')
          setError(res.error || '分类失败，请重试。')
        }
      } catch (e) {
        if (unmountedRef.current) return
        classifyRequestRef.current = null
        setClassifyState('failed')
        setError(toMessage(e))
      }
    }
    classifyTimerRef.current = window.setTimeout(tick, 0)
  }, [notify])

  const classify = useCallback(async () => {
    setClassifyState('running')
    setError(null)
    try {
      const result = await classifyMaterialInbox()
      if (unmountedRef.current) return
      setClassifyResult(result)
      if (result.status === 'pending' && result.request_id) {
        classifyRequestRef.current = result.request_id
        setClassifyState('waiting_gowrite')
        notify?.(result.message)
        void pollClassify(result.request_id)
      } else {
        setClassifyState('done')
        notify?.(result.message)
      }
    } catch (e) {
      setClassifyState('failed')
      setError(toMessage(e))
    }
  }, [notify, pollClassify])

  const cancelClassify = useCallback(async () => {
    const requestId = classifyRequestRef.current
    classifyRequestRef.current = null
    if (classifyTimerRef.current) window.clearTimeout(classifyTimerRef.current)
    if (requestId) {
      try { await cancelMaterialClassifyRequest(requestId) } catch { /* 幂等 */ }
    }
    setClassifyState('idle')
    setClassifyResult(null)
  }, [])

  // ---------------- 入库确认 ----------------

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

  // ---------------- 详情 / 提纯 / 蒸馏 ----------------

  const selectDetail = useCallback(async (assetId: string) => {
    setDetailLoading(true)
    setError(null)
    try {
      const d = await getMaterialDetail(assetId)
      if (!unmountedRef.current) setDetail(d)
    } catch (e) {
      if (!unmountedRef.current) setError(toMessage(e))
    } finally {
      if (!unmountedRef.current) setDetailLoading(false)
    }
  }, [])

  const runPrepare = useCallback(async (assetId: string) => {
    setBusyAssetId(assetId)
    setBusyKind('source_prepare')
    setError(null)
    try {
      const result = await runSourcePrepare(assetId)
      notify?.(result.message)
      await reload()
      if (detail?.id === assetId) await selectDetail(assetId)
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setBusyAssetId(null)
      setBusyKind(null)
    }
  }, [detail?.id, notify, reload, selectDetail])

  const pollDistill = useCallback(async (requestId: string) => {
    const tick = async () => {
      if (unmountedRef.current) return
      try {
        const res: BookDistillRequestStatus = await getBookDistillRequest(requestId)
        if (unmountedRef.current) return
        if (res.status === 'pending') {
          distillTimerRef.current = window.setTimeout(tick, POLL_INTERVAL_MS * 2)
          return
        }
        distillRequestRef.current = null
        setBusyAssetId(null)
        setBusyKind(null)
        if (res.status === 'completed') {
          notify?.(res.result?.message ?? '蒸馏完成')
          await reload()
          if (detail?.id) await selectDetail(detail.id)
        } else {
          setError(res.error || '蒸馏失败，请重试。')
        }
      } catch (e) {
        if (unmountedRef.current) return
        distillRequestRef.current = null
        setBusyAssetId(null)
        setBusyKind(null)
        setError(toMessage(e))
      }
    }
    distillTimerRef.current = window.setTimeout(tick, 0)
  }, [detail?.id, notify, reload, selectDetail])

  const runDistill = useCallback(async (assetId: string) => {
    setBusyAssetId(assetId)
    setBusyKind('book_distill')
    setError(null)
    try {
      const result = await runBookDistill(assetId)
      if (result.status === 'pending' && result.request_id) {
        distillRequestRef.current = result.request_id
        notify?.(result.message)
        void pollDistill(result.request_id)
        return true
      }
      notify?.(result.message)
      await reload()
      if (detail?.id === assetId) await selectDetail(assetId)
      return true
    } catch (e) {
      setBusyAssetId(null)
      setBusyKind(null)
      setError(toMessage(e))
      return false
    }
  }, [detail?.id, notify, pollDistill, reload, selectDetail])

  return {
    materials, loading, error, refreshing,
    inbox, inboxLoading, inboxError, applying,
    classifyState, classifyResult, importResult, importing,
    busyAssetId, busyKind, detail, detailLoading,
    reload, refresh, scanInbox, pickAndImport, classify, cancelClassify, confirmApply,
    selectDetail, runPrepare, runDistill,
  }
}
