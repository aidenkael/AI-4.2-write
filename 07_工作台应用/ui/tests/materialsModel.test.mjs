/**
 * materialsModel 纯函数测试（node:test；编译产物来自 tsconfig.tests.json）。
 *
 * 覆盖 CP1/CP2/CP3 作者工作流合同：
 * - 一级导航恰好四个（新增素材 / 已提纯素材库 / 写作素材库 / 素材总览）；
 * - 批次类型映射（原著/技巧类/其他 → REFERENCE_WORK/METHOD_SOURCE/LOOSE_MATERIAL）+ 无默认选择；
 * - 新增素材区唯一主按钮（提纯/保存素材）映射；
 * - workflow_stage 互斥派生 + needs_attention 停留在失败前阶段 + other 不进三生产区；
 * - book_0010 真实形态映射到 purified；
 * - 卡片信息行使用真实 format；needs_attention 重试动作；
 * - 导入 UI 无 AI 分类 / 识别 running 状态；作者 plan/confirm 生命周期已删除；一级刷新按钮已移除。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  MATERIAL_TOP_NAVIGATION,
  MATERIAL_TYPE_FILTERS,
  BATCH_TYPE_CHOICES,
  DEFAULT_BATCH_TYPE,
  inboxPrimaryAction,
  authorStateLabel,
  deriveWorkflowStage,
  materialsForStage,
  materialCardMeta,
  cardFormatLabel,
  attentionRetryLabel,
  workflowStageLabel,
  countMaterialsByType,
  matchesMaterialFilter,
  needsAttentionMaterials,
  pendingInboxBadgeCount,
  attachedMaterialName,
} from '../.test-build/features/materials/materialsModel.js'

// 后端投影形态的 MaterialItem：workflow_stage 由后端权威派生（前端消费，不再自造第二状态）。
const item = (over = {}) => ({
  id: 'book_x', name: '样例', type: 'REFERENCE_WORK', type_label: '原著', author: '',
  source_formats: ['EPUB'], author_group: 'pending', state: 'pending_prepare',
  workflow_stage: 'new', writing_callable: false, attention_message: null, ...over,
})

const pageSrc = readFileSync(new URL('../src/pages/MaterialsPage.tsx', import.meta.url), 'utf8')
const controllerSrc = readFileSync(new URL('../src/features/materials/useMaterialsController.ts', import.meta.url), 'utf8')

test('一级导航恰好四个：新增素材 / 已提纯素材库 / 写作素材库 / 素材总览', () => {
  assert.deepEqual([...MATERIAL_TOP_NAVIGATION], ['新增素材', '已提纯素材库', '写作素材库', '素材总览'])
  assert.deepEqual([...MATERIAL_TYPE_FILTERS], ['全部', '原著', '技巧类', '其他'])
})

test('batch type 映射正确：原著/技巧类/其他 → REFERENCE_WORK/METHOD_SOURCE/LOOSE_MATERIAL', () => {
  assert.deepEqual(BATCH_TYPE_CHOICES.map((c) => [c.label, c.value]), [
    ['原著', 'REFERENCE_WORK'],
    ['技巧类', 'METHOD_SOURCE'],
    ['其他', 'LOOSE_MATERIAL'],
  ])
  // 可选值只有这三项，没有第四个隐藏类型
  assert.deepEqual(BATCH_TYPE_CHOICES.map((c) => c.value), ['REFERENCE_WORK', 'METHOD_SOURCE', 'LOOSE_MATERIAL'])
})

test('batch type 没有默认选择：未选时主按钮 disabled', () => {
  assert.equal(DEFAULT_BATCH_TYPE, '')
  // 未选类型：主按钮 disabled（不猜默认类型、不请求后端）
  assert.deepEqual(inboxPrimaryAction(DEFAULT_BATCH_TYPE, false), { label: '入库', disabled: true })
})

test('新增素材区主按钮是「入库」（§4：不是提纯； intake 与 Prepare 分离）', () => {
  assert.deepEqual(inboxPrimaryAction('REFERENCE_WORK', false), { label: '入库', disabled: false })
  assert.deepEqual(inboxPrimaryAction('METHOD_SOURCE', false), { label: '入库', disabled: false })
  assert.deepEqual(inboxPrimaryAction('LOOSE_MATERIAL', false), { label: '入库', disabled: false })
  assert.deepEqual(inboxPrimaryAction('REFERENCE_WORK', true), { label: '正在入库…', disabled: true })
  // 绝不出现「提纯」作为入库主按钮文案
  for (const t of ['REFERENCE_WORK', 'METHOD_SOURCE', 'LOOSE_MATERIAL']) {
    assert.equal(inboxPrimaryAction(t, false).label.includes('提纯'), false)
  }
})

test('stage 互斥派生：pending_prepare→new、pending_distill→purified、ready→writing', () => {
  assert.equal(deriveWorkflowStage(item({ state: 'pending_prepare', workflow_stage: 'new' })), 'new')
  assert.equal(deriveWorkflowStage(item({ state: 'pending_distill', workflow_stage: 'purified' })), 'purified')
  assert.equal(deriveWorkflowStage(item({ state: 'ready', workflow_stage: 'writing' })), 'writing')
})

test('book_0010 奥术神座真实形态（提纯可用 / 知识未开始）映射到 purified', () => {
  const book0010 = item({
    id: 'book_0010', name: '奥术神座', state: 'pending_distill',
    workflow_stage: 'purified', source_formats: ['EPUB', 'TXT'],
  })
  assert.equal(deriveWorkflowStage(book0010), 'purified')
  assert.deepEqual(materialsForStage([book0010], 'purified'), [book0010])
  assert.deepEqual(materialsForStage([book0010], 'writing'), [])
  assert.deepEqual(materialsForStage([book0010], 'new'), [])
})

test('needs_attention 保持在失败前阶段（提纯失败=new；蒸馏/验收失败=purified）', () => {
  const purifyFailed = item({
    state: 'needs_attention', author_group: 'needs_attention', workflow_stage: 'new',
    attention_message: '资料需要检查后才能继续整理。',
  })
  const distillFailed = item({
    state: 'needs_attention', author_group: 'needs_attention', workflow_stage: 'purified',
    attention_message: '资料还需要检查，确认完成后才能用于写作。',
  })
  assert.equal(deriveWorkflowStage(purifyFailed), 'new')
  assert.equal(deriveWorkflowStage(distillFailed), 'purified')
  // needs_attention 不改变所属阶段：蒸馏失败项绝不出现在 new
  assert.deepEqual(materialsForStage([distillFailed], 'new'), [])
  assert.deepEqual(materialsForStage([distillFailed], 'purified'), [distillFailed])
  // 提纯失败项留在 new，绝不出现在 purified
  assert.deepEqual(materialsForStage([purifyFailed], 'purified'), [])
  assert.deepEqual(materialsForStage([purifyFailed], 'new'), [purifyFailed])
})

test('writing 素材不出现在 purified；purified 素材不出现在 new（三区互斥）', () => {
  const writing = item({ state: 'ready', workflow_stage: 'writing', writing_callable: true })
  const purified = item({ state: 'pending_distill', workflow_stage: 'purified' })
  const fresh = item({ state: 'pending_prepare', workflow_stage: 'new' })
  const all = [writing, purified, fresh]
  assert.deepEqual(materialsForStage(all, 'writing'), [writing])
  assert.deepEqual(materialsForStage(all, 'purified'), [purified])
  assert.deepEqual(materialsForStage(all, 'new'), [fresh])
  // 同一素材只属于一个阶段：三区之和 == 总数
  const total = materialsForStage(all, 'writing').length
    + materialsForStage(all, 'purified').length
    + materialsForStage(all, 'new').length
  assert.equal(total, all.length)
})

test('workflow_stage 支持 other：其他（LOOSE_MATERIAL；历史 RESEARCH）不进入三生产区', () => {
  const loose = item({ type: 'LOOSE_MATERIAL', type_label: '其他', state: 'pending_prepare', workflow_stage: 'other' })
  const research = item({ type: 'RESEARCH', type_label: '其他', state: 'pending_prepare', workflow_stage: 'other' })
  // deriveWorkflowStage 直接信任后端 other
  assert.equal(deriveWorkflowStage(loose), 'other')
  assert.equal(deriveWorkflowStage(research), 'other')
  // other 不进入 new/purified/writing 任一生产区
  for (const other of [loose, research]) {
    assert.deepEqual(materialsForStage([other], 'new'), [])
    assert.deepEqual(materialsForStage([other], 'purified'), [])
    assert.deepEqual(materialsForStage([other], 'writing'), [])
    assert.deepEqual(materialsForStage([other], 'other'), [other])
  }
  // other 与三区互斥：混合列表里三区之和绝不含 other
  const writing = item({ state: 'ready', workflow_stage: 'writing' })
  const all = [writing, loose, research]
  const productionTotal = materialsForStage(all, 'new').length
    + materialsForStage(all, 'purified').length
    + materialsForStage(all, 'writing').length
  assert.equal(productionTotal, 1, 'other 绝不计入 new/purified/writing')
  // 总览类型统计仍包含 other（LOOSE_MATERIAL / RESEARCH）
  assert.deepEqual(countMaterialsByType(all), { reference: 1, method: 0, other: 2 })
})

test('attentionRetryLabel：new→重新提纯、purified→重新蒸馏、writing→无', () => {
  assert.equal(attentionRetryLabel('new'), '重新提纯')
  assert.equal(attentionRetryLabel('purified'), '重新蒸馏')
  assert.equal(attentionRetryLabel('writing'), null)
  assert.equal(attentionRetryLabel(null), null)
})

test('素材总览：类型分布（原著/技巧类/其他）+ 阶段区域名', () => {
  assert.deepEqual(countMaterialsByType([
    item({ type: 'REFERENCE_WORK' }), item({ type: 'REFERENCE_WORK' }),
    item({ type: 'METHOD_SOURCE' }), item({ type: 'LOOSE_MATERIAL' }), item({ type: 'RESEARCH' }),
  ]), { reference: 2, method: 1, other: 2 })
  assert.equal(workflowStageLabel('new'), '新增素材')
  assert.equal(workflowStageLabel('purified'), '已提纯素材库')
  assert.equal(workflowStageLabel('writing'), '写作素材库')
  assert.equal(workflowStageLabel(null), '')
})

test('列表使用阶段对应格式（§8）：new=来源、purified=MD、writing=知识包（不混用）', () => {
  // new（待入库/待提纯）：原始来源格式
  assert.equal(materialCardMeta(item({ type_label: '原著', source_formats: ['EPUB'], author: '马伯庸', workflow_stage: 'new' })), '原著 · EPUB · 马伯庸')
  assert.equal(materialCardMeta(item({ type_label: '原著', source_formats: ['EPUB', 'TXT'], author: '', workflow_stage: 'new' })), '原著 · EPUB / TXT')
  assert.equal(materialCardMeta(item({ type_label: '技巧类', source_formats: ['PDF'], author: '', workflow_stage: 'new' })), '技巧类 · PDF')
  // purified（已提纯）：提纯结果 MD，不显示来源格式
  const purified = item({ type_label: '原著', source_formats: ['EPUB', 'TXT'], author: '', workflow_stage: 'purified', state: 'pending_distill', prepared_format: 'MD', prepared_available: true })
  assert.equal(cardFormatLabel(purified), 'MD')
  assert.equal(materialCardMeta(purified), '原著 · MD')
  // writing（写作素材库）：知识包表示，绝不混来源+MD
  const writing = item({ type_label: '原著', source_formats: ['EPUB', 'TXT'], author: '', workflow_stage: 'writing', state: 'ready', prepared_format: 'MD', knowledge_package_kind: 'BKP' })
  assert.equal(cardFormatLabel(writing), '知识包')
  const meta = materialCardMeta(writing)
  assert.equal(meta.includes('EPUB'), false, 'writing 卡不得混入来源格式')
  assert.equal(meta.includes('MD'), false, 'writing 卡不得混入提纯 MD 格式')
  const methodWriting = item({ type_label: '技巧类', workflow_stage: 'writing', state: 'ready', knowledge_package_kind: 'METHOD' })
  assert.equal(cardFormatLabel(methodWriting), '方法知识')
})

test('matchesMaterialFilter 二级筛选按真实 canonical 类型', () => {
  assert.equal(matchesMaterialFilter(item({ type: 'REFERENCE_WORK' }), '原著'), true)
  assert.equal(matchesMaterialFilter(item({ type: 'METHOD_SOURCE' }), '技巧类'), true)
  assert.equal(matchesMaterialFilter(item({ type: 'LOOSE_MATERIAL' }), '其他'), true)
  assert.equal(matchesMaterialFilter(item({ type: 'RESEARCH' }), '其他'), true)
  assert.equal(matchesMaterialFilter(item({ type: 'REFERENCE_WORK' }), '技巧类'), false)
  assert.equal(matchesMaterialFilter(item({ type: 'REFERENCE_WORK' }), '全部'), true)
})

test('导入 UI 无 AI 分类 / 识别 running 状态；改为批次机械入库计划', () => {
  for (const src of [pageSrc, controllerSrc]) {
    assert.equal(src.includes('controller.classify'), false, '不得残留 AI 分类调用')
    assert.equal(src.includes('material_classify'), false, '不得残留素材分类任务 kind')
    assert.equal(src.includes('classifyMaterial'), false)
    assert.equal(src.includes('get_material_classify'), false)
    assert.equal(src.includes('正在识别'), false, '不得再有“正在识别”AI 分类状态')
    assert.equal(src.includes('取消识别'), false)
  }
  // 批次机械计划 + MaterialIntake 事务入口存在（零 AI，后台内部实现）
  assert.ok(controllerSrc.includes('buildIntakePlan'), '批次机械入库计划入口存在')
  assert.ok(controllerSrc.includes('applyMaterialIntake'), 'MaterialIntake 事务入口存在')
  // 唯一作者批次动作存在（§4：只 intake，绝不自动 prepare）
  assert.ok(controllerSrc.includes('processInboxBatch'), '唯一作者批次动作 processInboxBatch 存在')
})

test('§4：入库动作不再自动提纯（processInboxBatch 不调用 prepareMaterial）', () => {
  const start = controllerSrc.indexOf('const processInboxBatch')
  assert.ok(start >= 0)
  const body = controllerSrc.slice(start, controllerSrc.indexOf('const runPrepare', start))
  assert.equal(body.includes('prepareMaterial'), false, '入库批次动作绝不自动提纯')
  assert.ok(body.includes('applyMaterialIntake'), '入库批次动作走 MaterialIntake 事务')
})

test('§11：distill 忙碌状态派生自 App 级任务（取消即清除，不持有第二套 local busy）', () => {
  assert.equal(controllerSrc.includes('setBusyKind'), false, '不得保留独立 distill busy setter')
  assert.equal(controllerSrc.includes('setBusyAssetId'), false, '不得保留独立 distill busy setter')
  assert.ok(controllerSrc.includes('distillBusyAssetId'), 'distill 忙碌状态从 App 级任务派生')
  assert.ok(controllerSrc.includes('prepareBusyAssetId'), '本页只拥有同步 Prepare 忙碌状态')
})

test('§13：新增素材区分「待入库」/「待提纯」；紧凑上传条取代 drop-zone', () => {
  assert.ok(pageSrc.includes('待入库'), '新增素材区含「待入库」分组')
  assert.ok(pageSrc.includes('待提纯'), '新增素材区含「待提纯」分组')
  assert.ok(pageSrc.includes('upload-bar'), '使用紧凑上传条')
  assert.equal(pageSrc.includes('drop-zone'), false, '不得保留过大 drop-zone')
})

test('作者 plan/confirm 生命周期与逐本类型 UI 已删除（不再有 updatePlanItem 作者模型）', () => {
  for (const src of [pageSrc, controllerSrc]) {
    assert.equal(src.includes('planState'), false, '不得残留 planState')
    assert.equal(src.includes('planResult'), false, '不得残留 planResult')
    assert.equal(src.includes('updatePlanItem'), false, '不得残留 updatePlanItem 作者模型')
    assert.equal(src.includes('confirmApply'), false, '不得残留确认入库动作')
    assert.equal(src.includes('dismissPlan'), false, '不得残留取消计划动作')
    assert.equal(src.includes('buildPlan'), false, '不得残留生成入库计划动作')
    assert.equal(src.includes('生成入库计划'), false)
    assert.equal(src.includes('确认入库'), false)
    assert.equal(src.includes('classify-plan'), false, '不得残留逐本 REVIEW 编辑 UI')
  }
  // MaterialsPage 不再 import 逐本类型相关 bridge 类型
  assert.equal(pageSrc.includes('MaterialAssetType'), false)
  assert.equal(pageSrc.includes('MaterialPlanItem'), false)
})

test('一级刷新按钮已移除；刷新状态只保留在素材总览', () => {
  assert.ok(pageSrc.includes('刷新状态'), '素材总览保留“刷新状态”')
  const toolbar = pageSrc.split('materials-toolbar')[1].split('</div>')[0]
  assert.equal(toolbar.includes('controller.refresh('), false, '一级工具条不得保留刷新按钮')
})

test('needs_attention 计入待处理徽标；attachment 名称回退安全', () => {
  const attention = item({ author_group: 'needs_attention', state: 'needs_attention', workflow_stage: 'new' })
  assert.deepEqual(needsAttentionMaterials([attention]), [attention])
  const inbox = [{ unsupported: false }, { unsupported: false }, { unsupported: true }]
  assert.equal(pendingInboxBadgeCount(inbox, [attention]), 3)
  assert.equal(attachedMaterialName('book_0035', [item({ id: 'book_0035', name: '长安十二时辰' })]), '长安十二时辰')
  assert.equal(attachedMaterialName('book_missing', []), 'book_missing')
})

test('state labels 保持作者可读', () => {
  assert.equal(authorStateLabel('pending_prepare'), '待提纯')
  assert.equal(authorStateLabel('pending_distill'), '待蒸馏')
  assert.equal(authorStateLabel('needs_attention'), '需要检查')
  assert.equal(authorStateLabel('ready'), '可用于写作')
})
