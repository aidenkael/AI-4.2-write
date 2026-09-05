import { CheckCircle2, FileUp, FolderSearch, RefreshCw, UploadCloud } from 'lucide-react'
import { useMemo, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { useApp } from '../features/app/AppStore'
import { useMaterialsController } from '../features/materials/useMaterialsController'
import type { MaterialAssetType, MaterialPlanItem } from '../bridge/client'
import {
  attachedMaterialName,
  attentionRetryLabel,
  authorStateLabel,
  BATCH_TYPE_CHOICES,
  MATERIAL_TOP_NAVIGATION,
  MATERIAL_TYPE_FILTERS,
  matchesMaterialFilter,
  materialCardMeta,
  materialsForStage,
  type MaterialTab,
} from '../features/materials/materialsModel'

export function MaterialsPage() {
  const { actions } = useApp()
  const controller = useMaterialsController({ notify: actions.notify })
  const [tab, setTab] = useState<MaterialTab>('新增素材')
  const [typeFilter, setTypeFilter] = useState('全部')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const newItems = useMemo(() => materialsForStage(controller.materials, 'new'), [controller.materials])
  const purifiedItems = useMemo(() => materialsForStage(controller.materials, 'purified'), [controller.materials])
  const writingItems = useMemo(() => materialsForStage(controller.materials, 'writing'), [controller.materials])
  const filteredWriting = useMemo(() => writingItems.filter((m) => matchesMaterialFilter(m, typeFilter)), [writingItems, typeFilter])

  const selected = controller.materials.find((m) => m.id === selectedId) ?? null
  const detail = controller.detail?.id === selectedId ? controller.detail : null
  const planItems = controller.planResult?.plan.items ?? []
  const hasInboxFiles = controller.inbox.some((file) => !file.unsupported)

  const tabIcons: Record<MaterialTab, typeof FileUp> = {
    '新增素材': FileUp,
    '已提纯素材库': FolderSearch,
    '写作素材库': CheckCircle2,
    '素材总览': RefreshCw,
  }
  const tabCounts: Record<MaterialTab, number> = {
    '新增素材': controller.inbox.length + newItems.length,
    '已提纯素材库': purifiedItems.length,
    '写作素材库': writingItems.length,
    '素材总览': controller.materials.length,
  }

  return <div className="page">
    <PageHeader title="素材与学习" subtitle="把原著和写作技巧整理成写作时可以调用的知识。" />
    <div className="filterbar panel materials-toolbar">
      {MATERIAL_TOP_NAVIGATION.map((label) => {
        const Icon = tabIcons[label]
        return <button key={label} className={tab === label ? 'active' : ''} onClick={() => { setTab(label); if (label === '新增素材') void controller.scanInbox() }}>
          <Icon size={15} /> {label}<small className="group-count">{tabCounts[label]}</small>
        </button>
      })}
    </div>
    {controller.loading && <div className="empty-state">正在加载资料…</div>}
    {controller.error && <p className="error-text">{controller.error}</p>}

    {tab === '新增素材' && <section className="materials-workflow">
      <div className="materials-left">
        <div className="panel materials-intake">
          <div className="drop-zone"><UploadCloud size={34} /><p><strong>选择本地资料</strong></p><p className="muted-note">支持 EPUB、TXT、PDF（单文件上限 200 MB）。</p><button className="primary" disabled={controller.importing} onClick={() => void controller.pickAndImport()}>{controller.importing ? '导入中…' : '选择文件'}</button></div>
          {controller.inboxLoading && <p className="muted-note">正在扫描收件箱…</p>}
          {controller.inboxError && <p className="error-text">{controller.inboxError}</p>}
          {controller.inbox.length > 0 && <div className="inbox-list">
            <h4>待入库文件 <small>（{controller.inbox.length}）</small></h4>
            {controller.inbox.map((file) => <div className="inbox-row" key={file.filename}>
              <strong className="inbox-name">{file.display_name || file.filename}</strong>
              <small className="muted-note">{file.format || file.suffix}</small>
              {file.unsupported && <small className="error-text">不支持的格式</small>}
              {file.exact_duplicate_matches.length > 0 && <small className="muted-note">重复：{file.exact_duplicate_matches.join('、')}</small>}
            </div>)}
          </div>}
          {hasInboxFiles && <div className="batch-type-selector">
            <h4>批次类型</h4>
            <div className="type-choices">
              {BATCH_TYPE_CHOICES.map((choice) => <button key={choice.value} className={controller.batchType === choice.value ? 'active' : ''} onClick={() => controller.setBatchType(choice.value)}>{choice.label}</button>)}
            </div>
            <button className="primary" disabled={controller.planState === 'building' || controller.applying} onClick={() => void controller.buildPlan()}>
              {controller.planState === 'building' ? '生成中…' : '生成入库计划'}
            </button>
          </div>}
          {controller.planState === 'done' && planItems.length > 0 && <section className="panel classify-plan">
            <h3>确认入库</h3>
            {planItems.map((item: MaterialPlanItem, index: number) => item.action === 'ATTACH_EXISTING'
              ? <p key={index}>将并入已有资料：<strong>《{attachedMaterialName(item.asset_id, controller.materials)}》</strong></p>
              : <div className="inbox-row" key={index}>
                <strong className="inbox-name">{item.name || item.files.join('、')}</strong>
                {item.action === 'REVIEW'
                  ? <><input value={item.name ?? ''} placeholder="资料名称" onChange={(event) => controller.updatePlanItem(index, { name: event.target.value })} />
                    <select value={item.type ?? ''} onChange={(event) => controller.updatePlanItem(index, { type: event.target.value as MaterialAssetType })}>
                      <option value="">请选择资料类型</option>
                      {BATCH_TYPE_CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                    </select></>
                  : <small className="muted-note">{BATCH_TYPE_CHOICES.find((c) => c.value === item.type)?.label ?? item.type}</small>}
              </div>)}
            <footer>
              <button className="primary" disabled={controller.applying} onClick={() => void controller.confirmApply()}>{controller.applying ? '入库中…' : '确认入库'}</button>
              <button className="secondary" onClick={controller.dismissPlan}>取消</button>
            </footer>
          </section>}
          {newItems.length > 0 && <div className="stage-materials">
            <h4>已入库待提纯 <small>（{newItems.length}）</small></h4>
            <div className="material-grid">
              {newItems.map((m) => <button key={m.id} className={selectedId === m.id ? 'material-card active' : 'material-card'} onClick={() => { setSelectedId(m.id); void controller.selectDetail(m.id) }}>
                <span className="material-card-title">{m.name}</span>
                <span className="material-card-meta">{materialCardMeta(m)}</span>
                <em className={m.state === 'needs_attention' ? 'warn' : 'wait'}>{authorStateLabel(m.state)}</em>
              </button>)}
            </div>
          </div>}
        </div>
      </div>
      <div className="materials-right">
        <section className="panel material-detail">
          <h3><FolderSearch /> 资料详情</h3>
          {selected && (controller.detailLoading || !detail) && <p className="muted-note">正在加载…</p>}
          {detail && <MaterialDetailPanel detail={detail} controller={controller} />}
          {!selected && <p className="muted-note">选择一份资料查看详情。</p>}
        </section>
      </div>
    </section>}

    {tab === '已提纯素材库' && <MaterialStagePanel
      items={purifiedItems}
      title="已提纯素材库"
      selectedId={selectedId}
      selected={selected}
      detail={detail}
      controller={controller}
      onSelect={(id) => { setSelectedId(id); void controller.selectDetail(id) }}
    />}

    {tab === '写作素材库' && <section className="materials-workflow">
      <div className="materials-left">
        <div className="materials-secondary-filter">
          {MATERIAL_TYPE_FILTERS.map((filter) => <button key={filter} className={typeFilter === filter ? 'active' : ''} onClick={() => setTypeFilter(filter)}>{filter}</button>)}
        </div>
        <section className="panel material-list">
          <h3>写作素材库 <small>（{filteredWriting.length}）</small></h3>
          <div className="material-grid">
            {filteredWriting.map((material) => <button key={material.id} className={selectedId === material.id ? 'material-card active' : 'material-card'} onClick={() => { setSelectedId(material.id); void controller.selectDetail(material.id) }}>
              <span className="material-card-title">{material.name}</span>
              <span className="material-card-meta">{materialCardMeta(material)}</span>
              <em className="ok">{authorStateLabel(material.state)}</em>
            </button>)}
          </div>
          {!controller.loading && filteredWriting.length === 0 && <div className="empty-state">这里暂时没有资料。</div>}
        </section>
      </div>
      <div className="materials-right">
        <section className="panel material-detail">
          <h3><FolderSearch /> 资料详情</h3>
          {selected && (controller.detailLoading || !detail) && <p className="muted-note">正在加载…</p>}
          {detail && <MaterialDetailPanel detail={detail} controller={controller} />}
          {!selected && <p className="muted-note">选择一份资料查看详情。</p>}
        </section>
      </div>
    </section>}

    {tab === '素材总览' && <section className="panel materials-overview">
      <h3>素材总览</h3>
      <div className="overview-grid">
        <div className="overview-card"><h4>新增素材</h4><span className="overview-count">{controller.inbox.length + newItems.length}</span><p className="muted-note">收件箱 + 待提纯</p></div>
        <div className="overview-card"><h4>已提纯</h4><span className="overview-count">{purifiedItems.length}</span><p className="muted-note">等待蒸馏</p></div>
        <div className="overview-card"><h4>可用于写作</h4><span className="overview-count">{writingItems.length}</span><p className="muted-note">蒸馏完成</p></div>
        <div className="overview-card"><h4>总计</h4><span className="overview-count">{controller.materials.length}</span><p className="muted-note">全部素材</p></div>
      </div>
      <button className="secondary" disabled={controller.refreshing} onClick={() => void controller.refresh()}>
        <RefreshCw /> {controller.refreshing ? '刷新中…' : '刷新状态'}
      </button>
    </section>}
  </div>
}

function MaterialDetailPanel({ detail, controller }: {
  detail: NonNullable<ReturnType<typeof useMaterialsController>['detail']>
  controller: ReturnType<typeof useMaterialsController>
}) {
  return <div className="material-answer">
    <h2>《{detail.name}》</h2>
    <p className="muted-note">
      {detail.type_label}{detail.author ? ` · ${detail.author}` : ''}
      {detail.source_formats.length ? ` · ${detail.source_formats.join(' / ')}` : ''}
    </p>
    {detail.state === 'pending_prepare' && <>
      <p>还没有整理原文。</p>
      <button className="primary" disabled={controller.busyAssetId !== null} onClick={() => void controller.runPrepare(detail.id)}>
        {controller.busyAssetId === detail.id ? '正在提纯…' : '提纯'}
      </button>
    </>}
    {detail.state === 'pending_distill' && <>
      <p>原文已整理，可以开始学习。</p>
      <button className="primary" disabled={controller.busyAssetId !== null} onClick={() => void controller.runDistill(detail.id)}>
        {controller.busyAssetId === detail.id ? '正在蒸馏…' : '蒸馏'}
      </button>
    </>}
    {detail.state === 'needs_attention' && <>
      <h3>需要检查</h3>
      <p>{detail.attention_message}</p>
      {attentionRetryLabel(detail.workflow_stage) && <button className="primary" disabled={controller.busyAssetId !== null}
        onClick={() => void (detail.workflow_stage === 'purified' ? controller.runDistill(detail.id) : controller.runPrepare(detail.id))}>
        {controller.busyAssetId === detail.id ? '处理中…' : attentionRetryLabel(detail.workflow_stage)}
      </button>}
    </>}
    {detail.state === 'ready' && <>
      <h3>✓ 可用于写作</h3>
      {detail.learning_summary && <h4>这本书主要可以学什么</h4>}
      {detail.learning_summary && <p>{detail.learning_summary}</p>}
      {detail.learning_sections.map((section) => <section key={section.title}><h4>{section.title}</h4><p>{section.body}</p></section>)}
    </>}
  </div>
}

function MaterialStagePanel({ items, title, selectedId, selected, detail, controller, onSelect }: {
  items: ReturnType<typeof useMaterialsController>['materials']
  title: string
  selectedId: string | null
  selected: ReturnType<typeof useMaterialsController>['materials'][number] | null
  detail: ReturnType<typeof useMaterialsController>['detail']
  controller: ReturnType<typeof useMaterialsController>
  onSelect: (id: string) => void
}) {
  return <section className="materials-workflow">
    <div className="materials-left">
      <section className="panel material-list">
        <h3>{title} <small>（{items.length}）</small></h3>
        <div className="material-grid">
          {items.map((material) => <button key={material.id} className={selectedId === material.id ? 'material-card active' : 'material-card'} onClick={() => onSelect(material.id)}>
            <span className="material-card-title">{material.name}</span>
            <span className="material-card-meta">{materialCardMeta(material)}</span>
            <em className={material.state === 'ready' ? 'ok' : material.state === 'needs_attention' ? 'warn' : 'wait'}>{authorStateLabel(material.state)}</em>
          </button>)}
        </div>
        {items.length === 0 && <div className="empty-state">这里暂时没有资料。</div>}
      </section>
    </div>
    <div className="materials-right">
      <section className="panel material-detail">
        <h3><FolderSearch /> 资料详情</h3>
        {selected && (controller.detailLoading || !detail) && <p className="muted-note">正在加载…</p>}
        {detail && <MaterialDetailPanel detail={detail} controller={controller} />}
        {!selected && <p className="muted-note">选择一份资料查看详情。</p>}
      </section>
    </div>
  </section>
}
