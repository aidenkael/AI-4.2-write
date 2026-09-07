/**
 * 素材工作流真实消费者控制器（App 级协调器消费者）。
 *
 * 作者工作流（§4：入库与提纯分离）：导入 EPUB/PDF/TXT → 选批次类型（原著/技巧类/其他）→
 * 点一次「入库」（确定性 intake：settles folder + ledger，绝不自动提纯）→
 * 原著/技巧类进入「待提纯」，作者在详情里逐本显式「提纯」；其他保存并退出提纯/蒸馏链。
 *
 * 生命周期归属（根不变量）：
 * - material_distill 的异步忙碌真相属于 App 级协调器任务（§11：本页派生，不持有第二套）；
 *   取消清除任务后可见忙碌状态立即消失；离开素材页任务继续、结果保留，返回后页面显式消费；
 * - 本页只拥有同步 Prepare 忙碌状态；buildIntakePlan / applyMaterialIntake / prepareMaterial 是确定性机械操作；
 * - 页面加载只读（listMaterials）+ 一次确定性收件箱扫描（零模型）；绝不隐式调用模型 / 提纯 / 蒸馏。
 */
import { useCallback, useEffect, useState } from 'react'
import {
  applyMaterialIntake,
  buildIntakePlan,
  getMaterialDetail,
  importMaterialFiles,
  listMaterials,
  openMaterialFolder,
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
  isAssetBusy(assetId: string): boolean
  busyKindForAsset(assetId: string): 'prepare' | 'distill' | null
  detail: MaterialDetail | null
  detailLoading: boolean
  openingFolderId: string | null
  reload(): Promise<void>
  refresh(): Promise<boolean>
  scanInbox(): Promise<void>
  pickAndImport(): Promise<ImportMaterialResult | null>
  setBatchType(batchType: string): void
  /** 唯一作者批次动作：机械 build plan → apply intake → reload+scan（§4：绝不自动提纯）。 */
  processInboxBatch(): Promise<boolean>
  selectDetail(assetId: string): Promise<void>
  openFolder(assetId: string): Promise<boolean>
  runPrepare(assetId: string): Promise<boolean>
  runDistill(assetId: string): Promise<boolean>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useMaterialsController(options?: { notify?: (message: string) => void }): MaterialsController {
  const notify = options?.notify
  const { tasksByRequestId, start, consume } = useAuthorTask()
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
  // §11：distill 忙碌真相属于 App 级协调器任务（下面派生）；本页只拥有同步 Prepare 忙碌状态。
  const [prepareBusyAssetId, setPrepareBusyAssetId] = useState<string | null>(null)
  const [detail, setDetail] = useState<MaterialDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [openingFolderId, setOpeningFolderId] = useState<string | null>(null)

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

  const distillTasks = Object.values(tasksByRequestId).filter((candidate) => candidate.kind === 'material_distill')
  const activeDistillAssetIds = new Set(distillTasks
    .filter((candidate) => candidate.status === 'running' || candidate.status === 'pending' || candidate.status === 'waiting_author')
    .map((candidate) => typeof candidate.meta?.asset_id === 'string' ? candidate.meta.asset_id : '')
    .filter(Boolean))
  const isAssetBusy = (assetId: string) => prepareBusyAssetId === assetId || activeDistillAssetIds.has(assetId)
  const busyKindForAsset = (assetId: string): 'prepare' | 'distill' | null => (
    prepareBusyAssetId === assetId ? 'prepare' : (activeDistillAssetIds.has(assetId) ? 'distill' : null)
  )

  useEffect(() => {
    for (const distillTask of distillTasks) {
      const assetId = typeof distillTask.meta?.asset_id === 'string' ? distillTask.meta.asset_id : null
      if (distillTask.status === 'candidate' && distillTask.result) {
        const result = distillTask.result as { message?: string }
        notify?.(result.message ?? '学习完成')
        void reload()
        if (detail?.id && detail.id === assetId) void selectDetail(detail.id)
        consume(distillTask.requestId)
      } else if (distillTask.status === 'failed') {
        setError(distillTask.error ?? '学习失败，请重试。')
        consume(distillTask.requestId)
      }
    }
  }, [tasksByRequestId, consume, detail?.id, notify, reload, selectDetail])

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

  // ---------------- 唯一作者批次动作：入库（机械、零 AI、绝不自动提纯） ----------------

  const processInboxBatch = useCallback(async () => {
    // 1. 未选批次类型：不请求后端
    if (!batchType) return false
    setProcessingInbox(true)
    setError(null)
    try {
      // 2. 机械构建入库计划（零 AI）
      const built = await buildIntakePlan(batchType)
      const plan = built.plan
      if (!plan?.items?.length) {
        setError('没有需要入库的文件。')
        return false
      }
      // 3. 存在 REVIEW（无法机械处理的文件）：不 apply，普通用户错误后结束
      if (plan.items.some((item) => item.action === 'REVIEW')) {
        setError('存在当前无法处理的文件，请移出后重新操作。')
        return false
      }
      // 4. §4：确定性 intake（settles folder + ledger），绝不自动调用 Prepare。
      //    原著/技巧类入库后进入「待提纯」；其他保存并退出提纯/蒸馏链。
      const result = await applyMaterialIntake(plan)
      await reload()
      await scanInbox()
      notify?.(batchType === 'LOOSE_MATERIAL' ? '素材已保存' : '素材已入库，可在「待提纯」中继续提纯')
      // 5. 成功后清空批次类型与导入回执
      setBatchType(DEFAULT_BATCH_TYPE)
      setImportResult(null)
      return result.ok
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setProcessingInbox(false)
    }
  }, [batchType, notify, reload, scanInbox])

  // ---------------- 详情 / 提纯（显式同步）/ 蒸馏（协调器任务） ----------------

  const runPrepare = useCallback(async (assetId: string) => {
    setPrepareBusyAssetId(assetId)
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
      setPrepareBusyAssetId(null)
    }
  }, [detail?.id, notify, reload, selectDetail])

  const runDistill = useCallback(async (assetId: string) => {
    setError(null)
    // §11：distill 忙碌状态由 App 级任务派生，不在本页设置第二套 local busy。
    const assetName = materials.find((item) => item.id === assetId)?.name
    const busy = await start({ kind: 'material_distill', asset_id: assetId, asset_name: assetName })
    if (busy) {
      setError(busy)
      return false
    }
    return true
  }, [materials, start])

  const openFolder = useCallback(async (assetId: string) => {
    setOpeningFolderId(assetId)
    setError(null)
    try {
      await openMaterialFolder(assetId)
      return true
    } catch (e) {
      setError(toMessage(e))
      return false
    } finally {
      setOpeningFolderId(null)
    }
  }, [])

  return {
    materials, loading, error, refreshing,
    inbox, inboxLoading, inboxError, processingInbox,
    batchType, importResult, importing,
    isAssetBusy, busyKindForAsset, detail, detailLoading, openingFolderId,
    reload, refresh, scanInbox, pickAndImport,
    setBatchType, processInboxBatch,
    selectDetail, openFolder, runPrepare, runDistill,
  }
}
