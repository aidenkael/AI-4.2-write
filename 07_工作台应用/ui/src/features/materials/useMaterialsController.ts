/**
 * 素材工作流真实消费者控制器（App 级协调器消费者）。
 *
 * 作者工作流（一次操作）：导入 EPUB/PDF/TXT → 选批次类型（原著/技巧类/其他）→
 * 原著/技巧类点一次「提纯」、其他点一次「保存素材」。
 * 「提纯」内部机械完成：build intake plan → MaterialIntake apply → 对本次 new_ids
 * 逐个调用现有 prepareMaterial → reload + scan（plan/apply 是后台内部实现，不再是作者步骤）。
 *
 * 生命周期归属（根不变量）：
 * - material_distill 的异步状态属于 App 级协调器；
 *   离开素材页任务继续、结果保留，返回后页面显式消费；
 * - buildIntakePlan / MaterialIntake apply / prepareMaterial 是确定性机械操作，留在本控制器；
 * - 页面加载只读（listMaterials）+ 一次确定性收件箱扫描（零模型）；
 *   绝不隐式调用模型 / 提纯 / 蒸馏。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  applyMaterialIntake,
  buildIntakePlan,
  getMaterialDetail,
  importMaterialFiles,
  listMaterials,
  pickMaterialFiles,
  prepareMaterial,
  refreshMaterials,
  scanMaterialInbox,
  type ImportMaterialResult,
  type MaterialDetail,
  type MaterialInboxFile,
  type MaterialItem,
} from '../../bridge/client'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'
import { DEFAULT_BATCH_TYPE } from './materialsModel'

export interface MaterialsController {
  materials: MaterialItem[]
  loading: boolean
  error: string | null
  refreshing: boolean
  inbox: MaterialInboxFile[]
  inboxLoading: boolean
  inboxError: string | null
  /** 新增素材区一次作者动作（提纯/保存）运行中；驱动主按钮进行中文案与 disabled。 */
  processingInbox: boolean
  batchType: string
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
  setBatchType(batchType: string): void
  /** 唯一作者批次动作：机械 build plan → apply → 对 new_ids 提纯 → reload+scan。 */
  processInboxBatch(): Promise<boolean>
  selectDetail(assetId: string): Promise<void>
  runPrepare(assetId: string): Promise<boolean>
  runDistill(assetId: string): Promise<boolean>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useMaterialsController(options?: { notify?: (message: string) => void }): MaterialsController {
  const notify = options?.notify
  const { task, start, consume } = useAuthorTask()
  const [materials, setMaterials] = useState<MaterialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [inbox, setInbox] = useState<MaterialInboxFile[]>([])
  const [inboxLoading, setInboxLoading] = useState(false)
  const [inboxError, setInboxError] = useState<string | null>(null)
  const [processingInbox, setProcessingInbox] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportMaterialResult | null>(null)
  const [batchType, setBatchType] = useState(DEFAULT_BATCH_TYPE)
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
    void scanInbox()
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

  // ---------------- 协调器任务 → 本页投影（distill only） ----------------

  const distillTask = task?.kind === 'material_distill' ? task : null

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

  // ---------------- 导入 / 批次计划 ----------------

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

  // ---------------- 唯一作者批次动作：一次完成 intake + prepare（机械，零 AI） ----------------

  const processInboxBatch = useCallback(async () => {
    // 1. 未选批次类型：不请求后端
    if (!batchType) return false
    setProcessingInbox(true)
    setError(null)
    try {
      // 2. 机械构建入库计划（零 AI）
      const built = await buildIntakePlan(batchType)
      const plan = built.plan
      // 3. 检查 plan
      if (!plan?.items?.length) {
        setError('没有需要处理的文件。')
        return false
      }
      // 4. 存在 REVIEW（无法机械处理的文件）：不 apply，普通用户错误后结束
      if (plan.items.some((item) => item.action === 'REVIEW')) {
        setError('存在当前无法处理的文件，请移出后重新操作。')
        return false
      }
      // 5. MaterialIntake 事务入库
      const result = await applyMaterialIntake(plan)
      // 6/7. 仅对本次新建的 REFERENCE_WORK / METHOD_SOURCE 逐个提纯；其他只保存
      const newIds = result.new_ids ?? []
      let prepared = 0
      const failed: string[] = []
      if (batchType === 'REFERENCE_WORK' || batchType === 'METHOD_SOURCE') {
        // 只 prepare new_ids（attached / exact duplicate 不重复提纯）；
        // 顺序执行不建并发框架；单本失败不阻断其余 new_ids
        for (const assetId of newIds) {
          try {
            await prepareMaterial(assetId)
            prepared += 1
          } catch {
            failed.push(assetId)
          }
        }
      }
      // 8. 无论单本提纯成败，最后统一 reload + scan（成功项自然进已提纯，失败项留新增）
      await reload()
      await scanInbox()
      if (result.git_warning) notify?.(result.git_warning)
      else if (batchType === 'LOOSE_MATERIAL') notify?.(result.message || '素材已保存')
      else if (failed.length === 0) notify?.('提纯完成')
      else notify?.(`已完成 ${prepared} 份，${failed.length} 份提纯失败，请在新增素材中重新处理。`)
      // 9. 成功后清空批次类型与导入回执
      setBatchType(DEFAULT_BATCH_TYPE)
      setImportResult(null)
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setProcessingInbox(false)
    }
  }, [batchType, notify, reload, scanInbox])

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
    inbox, inboxLoading, inboxError, processingInbox,
    batchType, importResult, importing,
    busyAssetId, busyKind, detail, detailLoading,
    reload, refresh, scanInbox, pickAndImport,
    setBatchType, processInboxBatch,
    selectDetail, runPrepare, runDistill,
  }
}
