import test from 'node:test'
import assert from 'node:assert/strict'

import {
  defaultNearTermRange,
  NEAR_TERM_MAX_SPAN,
  planningActionPayload,
  PLANNING_MODES,
  stageOptionsFromLengthPlan,
  validateNearTermRange,
} from '../.test-build/features/planning/planningModes.js'

test('全部规划模式都是同一操作的结构化范围', () => {
  assert.deepEqual([...PLANNING_MODES].sort(), ['book', 'free', 'impact_replan', 'near_term', 'stage'])
})

test('规划动作产生正确的模式 payload', () => {
  const book = planningActionPayload('proj_1', { mode: 'book' })
  assert.equal(book.error, null)
  assert.deepEqual(book.payload, { project_id: 'proj_1', author_question: '', planning_mode: 'book' })

  const stage = planningActionPayload('proj_1', { mode: 'stage', stageRef: 'gw2_stage_1' })
  assert.equal(stage.payload.stage_ref, 'gw2_stage_1')
  assert.equal(stage.payload.planning_mode, 'stage')

  const near = planningActionPayload('proj_1', { mode: 'near_term', chapterRange: [10, 14] })
  assert.deepEqual(near.payload.chapter_range, [10, 14])

  const free = planningActionPayload('proj_1', { mode: 'free', authorQuestion: ' 自由问题 ' })
  assert.deepEqual(free.payload, { project_id: 'proj_1', author_question: '自由问题', planning_mode: 'free' })
  assert.equal('stage_ref' in free.payload, false)
  assert.equal('chapter_range' in free.payload, false)
})

test('阶段选择器只使用稳定 ref，不暴露/推断标题', () => {
  const options = stageOptionsFromLengthPlan([
    { ref: 'gw2_stage_a', title: '第一卷' },
    { ref: '', title: '非法' },
    { title: '缺少 ref' },
    { ref: 'gw2_stage_b' },
  ])
  assert.deepEqual(options, [
    { ref: 'gw2_stage_a', title: '第一卷' },
    { ref: 'gw2_stage_b', title: '（未命名阶段）' },
  ])
  assert.deepEqual(stageOptionsFromLengthPlan(null), [])
})

test('近期范围默认值与边界校验作者可见', () => {
  assert.deepEqual(defaultNearTermRange(20), [20, 24])
  assert.deepEqual(defaultNearTermRange(0), [1, 5])
  assert.equal(validateNearTermRange(10, 14), null)
  assert.equal(validateNearTermRange(1, NEAR_TERM_MAX_SPAN), null)
  assert.ok(validateNearTermRange(1, NEAR_TERM_MAX_SPAN + 1)?.includes('12'))
  assert.ok(validateNearTermRange(14, 10)?.includes('结束章'))
  assert.ok(validateNearTermRange(0, 3)?.includes('正整数'))
})

test('非法输入返回错误而不是猜测范围', () => {
  assert.ok(planningActionPayload('proj_1', { mode: 'stage' }).error)
  assert.ok(planningActionPayload('proj_1', { mode: 'near_term' }).error)
  assert.ok(planningActionPayload('proj_1', { mode: 'near_term', chapterRange: [1, 99] }).error)
  assert.ok(planningActionPayload('', { mode: 'book' }).error)
})

test('impact_replan 保持显式：必须携带精确候选 id', () => {
  const ok = planningActionPayload('proj_1', { mode: 'impact_replan', impactCandidateIds: ['planning-impact-00000007'] })
  assert.deepEqual(ok.payload.impact_candidate_ids, ['planning-impact-00000007'])
  const missing = planningActionPayload('proj_1', { mode: 'impact_replan', impactCandidateIds: [] })
  assert.ok(missing.error?.includes('影响候选'))
})
