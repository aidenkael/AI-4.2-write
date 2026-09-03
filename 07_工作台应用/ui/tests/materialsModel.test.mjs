import test from 'node:test'
import assert from 'node:assert/strict'
import { MATERIAL_TOP_NAVIGATION, MATERIAL_TYPE_FILTERS, authorStateLabel, matchesMaterialFilter, pendingMaterials, updateClassifyPlanItem } from '../.test-build/features/materials/materialsModel.js'

const item = (type_label, state, author_group = 'pending') => ({ type_label, state, author_group })

test('materials author navigation has exactly three destinations', () => {
  assert.deepEqual(MATERIAL_TOP_NAVIGATION, ['待处理', '素材库', '可用于写作'])
  assert.deepEqual(MATERIAL_TYPE_FILTERS, ['全部', '原著', '技巧书', '其他'])
})

test('needs attention belongs to pending work and filters remain author-readable', () => {
  const attention = item('原著', 'needs_attention', 'needs_attention')
  assert.deepEqual(pendingMaterials([attention]), [attention])
  assert.equal(matchesMaterialFilter(item('研究资料', 'pending_prepare'), '其他'), true)
  assert.equal(matchesMaterialFilter(item('原著', 'pending_prepare'), '技巧书'), false)
})

test('state labels and running-free display remain bounded', () => {
  assert.equal(authorStateLabel('pending_prepare'), '待提纯')
  assert.equal(authorStateLabel('pending_distill'), '待蒸馏')
  assert.equal(authorStateLabel('needs_attention'), '需要检查')
  assert.equal(authorStateLabel('ready'), '可用于写作')
})

test('author correction turns a review proposal into a valid new asset', () => {
  const result = updateClassifyPlanItem({ action: 'REVIEW', files: ['x.epub'] }, { name: '资料名', type: 'METHOD_SOURCE' })
  assert.equal(result.action, 'NEW_ASSET')
  assert.equal(result.type, 'METHOD_SOURCE')
})
