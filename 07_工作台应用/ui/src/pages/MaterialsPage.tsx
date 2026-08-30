import { CheckCircle2, FileUp, FolderSearch, RefreshCw, Sparkles, UploadCloud, Wrench, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useApp } from '../features/app/AppStore'
import { useMaterialsController } from '../features/materials/useMaterialsController'
import { PageHeader } from '../components/PageHeader'

const typeLabels: Record<string, string> = {
  REFERENCE_WORK: '参考作品', METHOD_SOURCE: '方法/技巧资料', RESEARCH: '研究资料',
  LOOSE_MATERIAL: '零散素材', NEEDS_REVIEW: '待确认',
}

/**
 * 素材与学习：真实素材管理/加工工作流。
 *
 * 作者流程：本地导入 → 待入库 → 分类（确定性优先；无法定论时才一次 Agent）
 * → 确认入库（MaterialIntake 事务）→ 显式提纯 → 显式蒸馏 → 定稿知识包
 * → 可用于写作。UI 只传素材 id，后端按素材类型自动分派：
 * 参考作品 → SourcePrepare/BookDistill；方法/技巧资料 → MethodPrepare/MethodDistill。
 *
 * - 页面加载只读（listMaterials）；绝不隐式调用模型 / 提纯 / 蒸馏；
 * - 主导航是工作流阶段（待处理 / 素材库 / 可用于写作 / 需更新·异常），
 *   源类型与状态是次级筛选/详情；
 * - 素材页负责管理和加工；真正写作时由 Go Write 按当前问题自动检索已定稿的知识。
 */
export function MaterialsPage() {
  const { actions } = useApp()
  const controller = useMaterialsController({ notify: actions.notify })
  const [group, setGroup] = useState<'inbox' | 'all' | 'usable' | 'needs_update'>('inbox')
  const [typeFilter, setTypeFilter] = useState('全部')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const usable = useMemo(() => controller.materials.filter((m) => m.author_group === 'usable'), [controller.materials])
  const needsUpdate = useMemo(
    () => controller.materials.filter((m) => m.author_group === 'needs_update' || m.purification_status === '失败'),
    [controller.materials],
  )
  // 「素材库」= 整个 canonical 素材库（含可用于写作的素材，绝不排除）
  const all = useMemo(() => controller.materials, [controller.materials])

  const shown = useMemo(() => {
    const base = group === 'usable' ? usable : group === 'needs_update' ? needsUpdate : all
    return base.filter((m) => typeFilter === '全部' || (typeLabels[m.type] ?? m.type) === typeFilter)
  }, [all, group, needsUpdate, typeFilter, usable])

  const typeOptions = useMemo(() => {
    const set = new Set(controller.materials.map((m) => typeLabels[m.type] ?? m.type))
    return ['全部', ...Array.from(set)]
  }, [controller.materials])

  const selected = useMemo(
    () => controller.materials.find((m) => m.id === selectedId) ?? null,
    [controller.materials, selectedId],
  )

  const canClassify = controller.inbox.some((f) => !f.unsupported)
  const planItems = controller.classifyResult?.plan?.items ?? []

  const apply = async () => {
    if (await controller.confirmApply()) {
      setSelectedId(null)
    }
  }

  const count = (id: string) =>
    id === 'inbox' ? controller.inbox.filter((f) => !f.unsupported).length
      : id === 'usable' ? usable.length
        : id === 'needs_update' ? needsUpdate.length
          : all.length

  return (
    <div className="page">
      <PageHeader title="素材与学习" subtitle="导入素材 → 提纯 → 蒸馏 → 可用于写作；打开本页不会运行任何 AI。" />

      <div className="filterbar panel materials-toolbar">
        {([
          ['inbox', '待处理', FileUp],
          ['all', '素材库', FolderSearch],
          ['usable', '可用于写作', CheckCircle2],
          ['needs_update', '需更新/异常', Wrench],
        ] as const).map(([id, label, Icon]) => (
          <button key={id} className={group === id ? 'active' : ''} onClick={() => { setGroup(id); if (id === 'inbox') void controller.scanInbox() }}>
            <Icon size={15} /> {label}
            <small className="group-count">{count(id) ?? 0}</small>
          </button>
        ))}
        <button className="primary" disabled={controller.refreshing} onClick={() => void controller.refresh()}>
          <RefreshCw /> {controller.refreshing ? '刷新中…' : '刷新素材状态'}
        </button>
      </div>

      {controller.loading && <div className="empty-state">正在加载素材目录…</div>}
      {controller.error && <p className="error-text">{controller.error}</p>}

      {group === 'inbox' && (
        <section className="panel materials-intake">
          <div className="drop-zone">
            <UploadCloud size={34} />
            <p><strong>选择本地文件（EPUB / PDF / TXT 等）</strong></p>
            <p className="muted-note">所有文件先进入待入库收件箱，确认后才会正式入库。</p>
            <button className="primary" disabled={controller.importing} onClick={() => void controller.pickAndImport()}>
              {controller.importing ? '导入中…' : '选择文件'}
            </button>
          </div>

          <div className="learning">
            <p><strong>待处理</strong> = <code>01_原始素材/00_待入库</code> 中的文件（只读扫描事实，不自动分类）。</p>
            <p><strong>入库</strong>：先按确定性事实处理（重复文件并入已有素材、不支持类型人工确认）；只有无法定论的文件才会调用一次分类助手。它只给决策，绝不移动文件或改台账；确认后统一完成正式入库。</p>
            <p className="muted-note">素材页负责管理和加工；真正写作时由 Go Write 按当前问题自动检索已经蒸馏完成的知识。</p>
          </div>

          <div className="inbox-actions">
            <button className="secondary" disabled={controller.inboxLoading} onClick={() => void controller.scanInbox()}>
              {controller.inboxLoading ? '扫描中…' : '重新扫描待入库'}
            </button>
            <button
              className="primary"
              disabled={!canClassify || controller.classifyState === 'running' || controller.classifyState === 'waiting_gowrite' || controller.applying}
              onClick={() => void controller.classify()}
            >
              <Sparkles /> 分类并生成入库建议
            </button>
            {controller.classifyState === 'waiting_gowrite' && (
              <button className="secondary" onClick={() => void controller.cancelClassify()}>
                <X /> 取消分类
              </button>
            )}
          </div>

          {controller.inboxLoading && <p className="muted-note">正在扫描待入库目录…</p>}
          {controller.inboxError && <p className="error-text">{controller.inboxError}</p>}
          {!controller.inboxLoading && !controller.inboxError && controller.inbox.length === 0 && (
            <p className="muted-note">待入库目录暂无文件。</p>
          )}

          {controller.inbox.map((f) => (
            <div className="inbox-row" key={f.filename}>
              <div>
                <strong>{f.filename}</strong>
                {f.unsupported && <span className="soft-tag">不支持的类型</span>}
                {f.exact_duplicate_matches.length > 0 && (
                  <small className="muted-note">重复：{f.exact_duplicate_matches.join('、')}</small>
                )}
                {f.possible_existing_candidates.length > 0 && (
                  <small className="muted-note">可能属于：{f.possible_existing_candidates.join('、')}</small>
                )}
              </div>
            </div>
          ))}

          {controller.classifyState === 'running' && <div className="running"><span />正在分类待入库素材…</div>}
          {controller.classifyState === 'waiting_gowrite' && (
            <div className="running"><span />等待 Qoder /gowrite：正在分类待入库素材（一次分类）</div>
          )}
          {controller.classifyState === 'done' && planItems.length > 0 && (
            <section className="panel classify-plan">
              <header>
                <h3>入库建议（需你确认后才会执行）</h3>
              </header>
              <ul>
                {planItems.map((item, i) => {
                  const it = item as Record<string, unknown>
                  const files = Array.isArray(it.files) ? (it.files as string[]).join('、') : ''
                  const action = it.action === 'NEW_ASSET' ? '新建素材'
                    : it.action === 'ATTACH_EXISTING' ? `并入 ${it.asset_id ?? ''}`
                      : '人工确认'
                  return <li key={i}><strong>{action}</strong>：{files}{it.name ? `（名称：${it.name}）` : ''}</li>
                })}
              </ul>
              <footer>
                <button className="primary" disabled={controller.applying} onClick={() => void apply()}>
                  {controller.applying ? '入库中…' : '执行入库'}
                </button>
                <button className="secondary" onClick={() => { controller.cancelClassify(); setSelectedId(null) }}>不用了</button>
              </footer>
            </section>
          )}
          {controller.classifyState === 'done' && planItems.length === 0 && (
            <p className="muted-note">{controller.classifyResult?.message ?? '没有需要入库的文件。'}</p>
          )}
        </section>
      )}

      {group !== 'inbox' && (
        <>
          <div className="materials-secondary-filter muted-note">
            源类型：
            {typeOptions.map((t) => (
              <button key={t} className={typeFilter === t ? 'active' : ''} onClick={() => setTypeFilter(t)}>{t}</button>
            ))}
          </div>
          <div className="split materials-layout">
            <section className="panel material-list">
              <h3>{group === 'usable' ? '可用于写作' : group === 'needs_update' ? '需更新/异常' : '素材库'} <small>（{shown.length}）</small></h3>
              {shown.map((m) => (
                <button
                  key={m.id}
                  className={selectedId === m.id ? 'active' : ''}
                  onClick={() => { setSelectedId(m.id); void controller.selectDetail(m.id) }}
                >
                  <span className="material-thumb">{m.type === 'REFERENCE_WORK' ? '书' : m.type === 'METHOD_SOURCE' ? '方' : '研'}</span>
                  <span>
                    <strong>{m.name}</strong>
                    <small>{typeLabels[m.type] ?? m.type}{m.author ? `　·　${m.author}` : ''}</small>
                  </span>
                  <em className={m.writing_callable ? 'ok' : 'wait'}>{m.writing_callable ? '可调用' : '待加工'}</em>
                </button>
              ))}
              {!controller.loading && shown.length === 0 && <div className="empty-state">这个分组暂时没有素材。</div>}
            </section>

            <section className="panel material-detail">
              <h3><FolderSearch /> 素材说明</h3>
              {selected && (
                <div className="material-answer">
                  <p><strong>写作时能否调用？</strong>{selected.writing_callable ? '是（按需检索）' : '否'}</p>
                  <p><strong>当前为什么？</strong>{selected.why}</p>
                  <p><strong>当前阶段：</strong>
                    {selected.knowledge_status === '可用' ? '蒸馏完成，可用于写作'
                      : selected.purification_status === '可用' ? '提纯完成，待蒸馏'
                        : selected.purification_status === '失败' ? '处理失败'
                          : selected.purification_status === '需复核' ? '需人工处理'
                            : '已入库，待提纯'}
                  </p>
                  <p><strong>下一步是什么？</strong>{selected.next_step}</p>
                  <p className="muted-note">
                    类型：{typeLabels[selected.type] ?? selected.type} · 提纯：{selected.purification_status} · 知识：{selected.knowledge_status}
                    {selected.notes ? ` · 备注：${selected.notes}` : ''}
                  </p>
                  <div className="material-actions">
                    {selected.purification_status !== '可用' && selected.type !== 'LOOSE_MATERIAL' && selected.type !== 'NEEDS_REVIEW' && (
                      <button
                        className="secondary"
                        disabled={controller.busyAssetId !== null}
                        onClick={() => void controller.runPrepare(selected.id)}
                      >
                        {controller.busyAssetId === selected.id && controller.busyKind === 'prepare' ? '提纯中…' : '提纯'}
                      </button>
                    )}
                    {selected.purification_status === '可用' && selected.knowledge_status !== '可用' && (
                      <button
                        className="primary"
                        disabled={controller.busyAssetId !== null}
                        onClick={() => void controller.runDistill(selected.id)}
                      >
                        {controller.busyAssetId === selected.id && controller.busyKind === 'distill' ? '蒸馏中…' : '蒸馏'}
                      </button>
                    )}
                    {controller.busyAssetId === selected.id && controller.busyKind === 'distill' && (
                      <span className="muted-note">显式离线处理，可能耗时较长；完成后自动生成可检索的知识包。</span>
                    )}
                  </div>
                  <p className="muted-note">提示：素材页负责管理和加工；真正写作时由 Go Write 按当前问题自动检索已经定稿的知识。不会因为打开本页而运行任何 AI 或提纯/蒸馏。</p>
                </div>
              )}
              {!selected && (
                <div className="learning">
                  <p>素材目录来自正式素材资产台账。打开本页不会运行任何 AI 或提纯/蒸馏过程。</p>
                  <p>选择一个素材查看：它写作时能否被调用、当前阶段、下一步该做什么。</p>
                  <ul>
                    <li>「可用于写作」= 已蒸馏出定稿知识包，写作/规划/检查时按需检索。</li>
                    <li>「提纯」把素材标准化为纯净 Markdown（确定性、无模型；后端按类型自动选择处理方式）。</li>
                    <li>「蒸馏」把提纯完成的素材蒸馏为知识包（显式离线处理，完成后才标注可用）。</li>
                  </ul>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
