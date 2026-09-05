/**
 * materialsModel 纯函数测试（node:test；编译产物来自 tsconfig.tests.json）。
 *
 * 覆盖 CP1/CP2/CP3 作者工作流合同：
 * - 一级导航恰好四个（新增素材 / 已提纯素材库 / 写作素材库 / 素材总览）；
 * - 批次类型映射（原著/技巧类/其他 → REFERENCE_WORK/METHOD_SOURCE/LOOSE_MATERIAL）；
 * - workflow_stage 互斥派生 + needs_attention 停留在失败前阶段；
 * - book_0010 真实形态映射到 purified；
 * - 卡片信息行使用真实 format；needs_attention 重试动作；
 * - 导入 UI 无 AI 分类 / 识别 running 状态；一级刷新按钮已移除。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  MATERIAL_TOP_NAVIGATION,
  MATERIAL_TYPE_FILTERS,
  BATCH_TYPE_CHOICES,
  authorStateLabel,
  deriveWorkflowStage,
  materialsForStage,
  materialCardMeta,
  attentionRetryLabel,
  matchesMaterialFilter,
  needsAttentionMaterials,
  pendingInboxBadgeCount,
  attachedMaterialName,
  updatePlanItem,
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

test('attentionRetryLabel：new→重新提纯、purified→重新蒸馏、writing→无', () => {
  assert.equal(attentionRetryLabel('new'), '重新提纯')
  assert.equal(attentionRetryLabel('purified'), '重新蒸馏')
  assert.equal(attentionRetryLabel('writing'), null)
  assert.equal(attentionRetryLabel(null), null)
})

test('列表使用真实 format：卡片信息行 = 类型 · 格式 · 作者', () => {
  assert.equal(materialCardMeta(item({ type_label: '原著', source_formats: ['EPUB'], author: '马伯庸' })), '原著 · EPUB · 马伯庸')
  assert.equal(materialCardMeta(item({ type_label: '原著', source_formats: ['EPUB', 'TXT'], author: '' })), '原著 · EPUB / TXT')
  assert.equal(materialCardMeta(item({ type_label: '技巧书', source_formats: ['PDF'], author: '' })), '技巧书 · PDF')
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
  // 批次机械计划 + MaterialIntake 事务入口存在（零 AI）
  assert.ok(controllerSrc.includes('buildIntakePlan'), '批次机械入库计划入口存在')
  assert.ok(controllerSrc.includes('applyMaterialIntake'), 'MaterialIntake 事务入口存在')
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

test('作者补全名称/类型后 REVIEW 升级为 NEW_ASSET', () => {
  const result = updatePlanItem({ action: 'REVIEW', files: ['x.epub'] }, { name: '资料名', type: 'METHOD_SOURCE' })
  assert.equal(result.action, 'NEW_ASSET')
  assert.equal(result.type, 'METHOD_SOURCE')
  assert.equal(result.reason, undefined)
})
