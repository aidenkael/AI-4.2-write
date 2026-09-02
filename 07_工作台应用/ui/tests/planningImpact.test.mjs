import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ACTIVE_IMPACT_STATUSES,
  deferCandidatePayload,
  formatAffectedChapters,
  impactNoticeText,
  impactReplanPayload,
  impactRowText,
  resolveStageTitles,
  restoreCandidatePayload,
  unresolvedImpactCandidates,
} from '../.test-build/features/planning/planningImpact.js'

test('Overview 紧凑影响指示只给作者可读计数', () => {
  assert.equal(impactNoticeText(3), '有 3 项作者修改可能影响后续规划')
  assert.equal(impactNoticeText(0), null)
  assert.equal(impactNoticeText(1.5), null)
})

test('章节范围合并为连续段且其余顿号分隔', () => {
  assert.equal(formatAffectedChapters([48, 49, 50, 51, 52, 53]), '第 48–53 章')
  assert.equal(formatAffectedChapters([48, 51, 52]), '第 48 章、第 51–52 章')
  assert.equal(formatAffectedChapters([]), null)
})

test('候选行只呈现摘要与影响范围，绝不暴露 raw ref', () => {
  const stages = [{ ref: 'gw2_stage_ref_1', title: '宗门内斗' }]
  const views = unresolvedImpactCandidates([
    {
      candidate_id: 'planning-impact-00000007',
      summary: '人物关系调整可能影响后续规划',
      status: 'pending_author',
      affected_chapter_numbers: [48, 49, 50, 51, 52, 53],
      affected_stage_refs: ['gw2_stage_ref_1'],
      affected_refs: ['gw2_obj_abc_00000001'],
    },
    { candidate_id: 'planning-impact-00000008', summary: '已解决', status: 'resolved' },
  ])
  assert.equal(views.length, 1)
  const text = impactRowText(views[0], stages)
  assert.equal(text, '人物关系调整可能影响后续规划（可能影响 第 48–53 章 与 阶段「宗门内斗」）')
  assert.ok(!text.includes('gw2_'), '作者可见文本绝不包含 raw ref')
  assert.ok(!text.includes('planning-impact'), '作者可见文本绝不包含内部候选 id')
})

test('无法解析的阶段绝不回退显示原始 ref', () => {
  assert.deepEqual(resolveStageTitles(['gw2_stage_missing'], [{ ref: 'gw2_stage_1', title: '卷一' }]), [])
})

test('重规划 payload 精确携带选中候选 id 与模式', () => {
  const payload = impactReplanPayload('proj_1', ['planning-impact-00000007', '', 'planning-impact-00000009'])
  assert.deepEqual(payload, {
    project_id: 'proj_1',
    author_question: '',
    planning_mode: 'impact_replan',
    impact_candidate_ids: ['planning-impact-00000007', 'planning-impact-00000009'],
  })
})

test('暂时保留只是状态转换，不是生成请求', () => {
  const payload = deferCandidatePayload('proj_1', 'planning-impact-00000007')
  assert.deepEqual(payload, {
    project_id: 'proj_1',
    candidate_id: 'planning-impact-00000007',
    status: 'deferred',
  })
  assert.equal('planning_mode' in payload, false, 'defer 绝不携带规划模式 → 绝不触发 StoryPlan')
  const restore = restoreCandidatePayload('proj_1', 'planning-impact-00000007')
  assert.equal(restore.status, 'pending_author')
})

test('只暴露待作者处置的候选；已解决/已作废不出现', () => {
  const views = unresolvedImpactCandidates([
    { candidate_id: 'a', summary: '待处理', status: 'pending_author' },
    { candidate_id: 'b', summary: '暂缓', status: 'deferred' },
    { candidate_id: 'c', summary: '已解决', status: 'resolved' },
    { candidate_id: 'd', summary: '已作废', status: 'obsolete' },
    { candidate_id: 'e', summary: '' },
  ])
  assert.deepEqual(views.map((view) => view.candidateId), ['a', 'b'])
  assert.deepEqual([...ACTIVE_IMPACT_STATUSES].sort(), ['deferred', 'in_replan', 'pending_author'])
})
