/**
 * taskModel 纯函数测试（node:test；编译产物来自 tsconfig.tests.json）。
 * 覆盖任务条投影 / 状态派生 / 目标页 / 活跃判断 / 审计 key。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  taskLabel,
  taskTarget,
  deriveTaskStatus,
  waitingAuthorMessage,
  candidateReadyMessage,
  taskStripView,
  isTaskActive,
  auditEventKey,
} from '../.test-build/features/tasks/taskModel.js'

test('taskLabel covers all kinds', () => {
  assert.equal(taskLabel('story_write'), '正文写作')
  assert.equal(taskLabel('book_distill'), '素材蒸馏')
})

test('taskTarget maps to owning page/section', () => {
  assert.deepEqual(taskTarget('story_write'), { section: 'writing' })
  assert.deepEqual(taskTarget('new_project'), { page: 'projects' })
  assert.deepEqual(taskTarget('material_classify'), { page: 'materials' })
  assert.deepEqual(taskTarget('review'), { section: 'review' })
})

test('deriveTaskStatus: interactive pending → waiting_author; direct → running', () => {
  assert.equal(deriveTaskStatus('story_plan', 'pending', null, 'interactive_bridge'), 'waiting_author')
  assert.equal(deriveTaskStatus('story_plan', 'pending', null, 'direct'), 'running')
  assert.equal(deriveTaskStatus('story_write', 'pending', 'pending_prose', 'interactive_bridge'), 'waiting_author')
  // 交互阶段即使 execution_mode 缺失也按阶段识别（resume 场景）
  assert.equal(deriveTaskStatus('story_write', 'pending', 'pending_selection', null), 'waiting_author')
  assert.equal(deriveTaskStatus('story_write', 'completed', null, 'direct'), 'candidate')
  assert.equal(deriveTaskStatus('review', 'canceled', null, 'direct'), 'canceled')
  assert.equal(deriveTaskStatus('review', 'expired', null, 'direct'), 'failed')
  assert.equal(deriveTaskStatus('review', 'weird', null, 'direct'), 'failed')
})

test('waitingAuthorMessage: stage-specific, never fabricated', () => {
  assert.ok(waitingAuthorMessage('story_write', 'pending_prose').includes('再次执行 /gowrite'))
  assert.ok(waitingAuthorMessage('story_write', null).includes('正在选择本次写作上下文'))
  assert.ok(waitingAuthorMessage('story_plan', null).includes('/gowrite'))
})

test('candidateReadyMessage is truthful per kind', () => {
  assert.equal(candidateReadyMessage('story_write'), '正文候选已生成 · 返回查看')
  assert.equal(candidateReadyMessage('review'), '检查报告已生成 · 返回查看')
})

test('taskStripView: waiting_author → gowrite primary action', () => {
  const view = taskStripView({
    kind: 'story_write', requestId: 'r', projectId: 'p', status: 'waiting_author',
    phase: 'pending_prose', message: '上下文已准备好，请再次执行 /gowrite 生成正文',
    execution: { execution_mode: 'interactive_bridge' }, result: null, error: null,
  })
  assert.equal(view.label, '正文写作')
  assert.equal(view.primaryAction, 'gowrite')
  assert.equal(view.primaryLabel, '前往 Qoder 执行 /gowrite')
  assert.ok(view.stateText.includes('再次执行 /gowrite'))
  assert.equal(view.canCancel, true)
})

test('taskStripView: running → return action with direct-mode secondary detail', () => {
  const view = taskStripView({
    kind: 'story_plan', requestId: 'r', projectId: null, status: 'running',
    phase: null, message: null, execution: { execution_mode: 'direct' }, result: null, error: null,
  })
  assert.equal(view.primaryAction, 'return')
  assert.ok(view.stateText.includes('后台 AI 正在执行'))
  assert.ok(view.stateText.includes('直接模式'))
})

test('taskStripView: candidate → 返回查看; failed shows real error; confirming no cancel', () => {
  const candidate = taskStripView({
    kind: 'new_project', requestId: 'r', projectId: null, status: 'candidate',
    phase: null, message: null, execution: null, result: {}, error: null,
  })
  assert.equal(candidate.primaryLabel, '返回查看')
  assert.equal(candidate.canCancel, true)
  const failed = taskStripView({
    kind: 'review', requestId: 'r', projectId: 'p', status: 'failed',
    phase: null, message: null, execution: null, result: null, error: '模型执行出错',
  })
  assert.equal(failed.stateText, '模型执行出错')
  const confirming = taskStripView({
    kind: 'story_write', requestId: 'r', projectId: 'p', status: 'confirming',
    phase: null, message: null, execution: null, result: null, error: null,
  })
  assert.equal(confirming.canCancel, false)
})

test('isTaskActive: failed/canceled not active (可被重试替换)', () => {
  assert.equal(isTaskActive('running'), true)
  assert.equal(isTaskActive('waiting_author'), true)
  assert.equal(isTaskActive('candidate'), true)
  assert.equal(isTaskActive('failed'), false)
  assert.equal(isTaskActive('canceled'), false)
})

test('auditEventKey: event_id 优先，旧版回退 seq', () => {
  assert.equal(auditEventKey({ event_id: 'abc', seq: 3 }), 'abc')
  assert.equal(auditEventKey({ seq: 3 }), 'seq:3')
  assert.equal(auditEventKey({ event_id: '', seq: 4 }), 'seq:4')
})
