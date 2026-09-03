import { CheckCircle2, FileUp, FolderSearch, RefreshCw, Sparkles, UploadCloud, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { useApp } from '../features/app/AppStore'
import { useMaterialsController } from '../features/materials/useMaterialsController'
import type { MaterialAssetType } from '../bridge/client'
import { authorStateLabel, MATERIAL_TYPE_FILTERS, matchesMaterialFilter, pendingMaterials } from '../features/materials/materialsModel'

const typeChoices: Array<{ value: MaterialAssetType; label: string }> = [
  { value: 'REFERENCE_WORK', label: '原著' }, { value: 'METHOD_SOURCE', label: '技巧书' },
  { value: 'RESEARCH', label: '研究资料' }, { value: 'LOOSE_MATERIAL', label: '零散素材' },
]

export function MaterialsPage() {
  const { actions } = useApp()
  const controller = useMaterialsController({ notify: actions.notify })
  const [group, setGroup] = useState<'inbox' | 'library' | 'ready'>('inbox')
  const [typeFilter, setTypeFilter] = useState('全部')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const pending = useMemo(() => pendingMaterials(controller.materials), [controller.materials])
  const ready = useMemo(() => controller.materials.filter((m) => m.state === 'ready'), [controller.materials])
  const base = group === 'ready' ? ready : controller.materials
  const shown = useMemo(() => base.filter((m) => matchesMaterialFilter(m, typeFilter)), [base, typeFilter])
  const selected = controller.materials.find((m) => m.id === selectedId) ?? null
  const detail = controller.detail?.id === selectedId ? controller.detail : null
  const planItems = controller.classifyResult?.plan.items ?? []
  const canClassify = controller.inbox.some((file) => !file.unsupported)

  return <div className="page">
    <PageHeader title="素材与学习" subtitle="把原著和写作技巧整理成写作时可以调用的知识。" />
    <div className="filterbar panel materials-toolbar">
      {([
        ['inbox', '待处理', FileUp, controller.inbox.filter((file) => !file.unsupported).length + pending.length],
        ['library', '素材库', FolderSearch, controller.materials.length], ['ready', '可用于写作', CheckCircle2, ready.length],
      ] as const).map(([id, label, Icon, count]) => <button key={id} className={group === id ? 'active' : ''} onClick={() => { setGroup(id); if (id === 'inbox') void controller.scanInbox() }}><Icon size={15} /> {label}<small className="group-count">{count}</small></button>)}
      <button className="secondary" disabled={controller.refreshing} onClick={() => void controller.refresh()}><RefreshCw /> {controller.refreshing ? '刷新中…' : '刷新'}</button>
    </div>
    {controller.loading && <div className="empty-state">正在加载资料…</div>}
    {controller.error && <p className="error-text">{controller.error}</p>}

    {group === 'inbox' && <section className="panel materials-intake">
      <div className="drop-zone"><UploadCloud size={34} /><p><strong>选择本地资料</strong></p><p className="muted-note">推荐 EPUB；也支持 TXT 和带文字层的 PDF。</p><button className="primary" disabled={controller.importing} onClick={() => void controller.pickAndImport()}>{controller.importing ? '导入中…' : '选择文件'}</button></div>
      <div className="inbox-actions"><button className="secondary" disabled={controller.inboxLoading} onClick={() => void controller.scanInbox()}>{controller.inboxLoading ? '扫描中…' : '识别资料'}</button><button className="primary" disabled={!canClassify || controller.classifyState === 'running' || controller.classifyState === 'waiting_gowrite' || controller.applying} onClick={() => void controller.classify()}><Sparkles /> 识别资料</button>{controller.classifyState === 'waiting_gowrite' && <button className="secondary" onClick={() => void controller.cancelClassify()}><X /> 取消</button>}</div>
      {controller.inboxLoading && <p className="muted-note">正在识别资料…</p>}{controller.inboxError && <p className="error-text">{controller.inboxError}</p>}
      {controller.inbox.map((file) => <div className="inbox-row" key={file.filename}><strong>{file.filename}</strong>{file.unsupported && <small className="muted-note">当前格式需要检查</small>}</div>)}
      {(controller.classifyState === 'running' || controller.classifyState === 'waiting_gowrite') && <div className="running"><span />正在识别资料…</div>}
      {controller.classifyState === 'done' && planItems.length > 0 && <section className="panel classify-plan"><h3>确认入库</h3>{planItems.map((item, index) => item.action === 'ATTACH_EXISTING' ? <p key={index}>将并入已有资料：<strong>《{item.asset_id}》</strong></p> : <div className="inbox-row" key={index}><strong>{item.files.join('、')}</strong><input value={item.name ?? ''} placeholder="资料名称" onChange={(event) => controller.updateClassifyItem(index, { name: event.target.value })} /><select value={item.type ?? ''} onChange={(event) => controller.updateClassifyItem(index, { type: event.target.value as MaterialAssetType })}><option value="">请选择资料类型</option>{typeChoices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select></div>)}<footer><button className="primary" disabled={controller.applying} onClick={() => void controller.confirmApply()}>{controller.applying ? '入库中…' : '确认入库'}</button><button className="secondary" onClick={() => void controller.cancelClassify()}>取消</button></footer></section>}
      {pending.some((m) => m.author_group === 'needs_attention') && <section className="learning"><h3>需要检查的已有资料</h3>{pending.filter((m) => m.author_group === 'needs_attention').map((m) => <p key={m.id}>《{m.name}》：{m.attention_message}</p>)}</section>}
    </section>}

    {group !== 'inbox' && <><div className="materials-secondary-filter">{MATERIAL_TYPE_FILTERS.map((filter) => <button key={filter} className={typeFilter === filter ? 'active' : ''} onClick={() => setTypeFilter(filter)}>{filter}</button>)}</div><div className="split materials-layout"><section className="panel material-list"><h3>{group === 'ready' ? '可用于写作' : '素材库'} <small>（{shown.length}）</small></h3>{shown.map((material) => <button key={material.id} className={selectedId === material.id ? 'active' : ''} onClick={() => { setSelectedId(material.id); void controller.selectDetail(material.id) }}><span className="material-thumb">书</span><span><strong>{material.name}</strong><small>{material.type_label}{material.author ? ` · ${material.author}` : ''}</small></span><em className={material.state === 'ready' ? 'ok' : 'wait'}>{authorStateLabel(material.state)}</em></button>)}{!controller.loading && shown.length === 0 && <div className="empty-state">这里暂时没有资料。</div>}</section>
      <section className="panel material-detail"><h3><FolderSearch /> 资料详情</h3>{selected && (controller.detailLoading || !detail) && <p className="muted-note">正在加载…</p>}{detail && <div className="material-answer"><h2>《{detail.name}》</h2><p className="muted-note">{detail.type_label}{detail.author ? ` · ${detail.author}` : ''}{detail.source_formats.length ? ` · ${detail.source_formats.join(' / ')}` : ''}</p>{detail.state === 'pending_prepare' && <><p>还没有整理原文。</p><button className="primary" disabled={controller.busyAssetId !== null} onClick={() => void controller.runPrepare(detail.id)}>{controller.busyAssetId === detail.id ? '正在提纯…' : '提纯'}</button></>}{detail.state === 'pending_distill' && <><p>原文已整理，可以开始学习。</p><button className="primary" disabled={controller.busyAssetId !== null} onClick={() => void controller.runDistill(detail.id)}>{controller.busyAssetId === detail.id ? '正在蒸馏…' : '蒸馏'}</button></>}{detail.state === 'needs_attention' && <><h3>需要检查</h3><p>{detail.attention_message}</p></>}{detail.state === 'ready' && <><h3>✓ 可用于写作</h3><h4>这本书主要可以学什么</h4>{detail.learning_summary && <p>{detail.learning_summary}</p>}{detail.learning_sections.map((section) => <section key={section.title}><h4>{section.title}</h4><p>{section.body}</p></section>)}</>}</div>}{!selected && <p className="muted-note">选择一份资料查看详情。</p>}</section></div></>}
  </div>
}
