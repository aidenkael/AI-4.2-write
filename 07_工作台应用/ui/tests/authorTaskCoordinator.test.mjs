import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  dropTask, patchRequestTask, putTask, startConflict, taskList, waitingPhaseKey,
} from '../.test-build/features/tasks/coordinatorModel.js'
import { taskStripView } from '../.test-build/features/tasks/taskModel.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = path.resolve(here, '..', 'src')

function material(requestId, assetId, status = 'waiting_author', phase = null, command = `/server-command-${requestId}`) {
  return {
    kind: 'material_distill', requestId, projectId: null, status, phase,
    message: null, execution: { execution_mode: 'interactive_bridge', agent_command: command },
    result: null, error: null, meta: { asset_id: assetId },
  }
}

function exclusive(requestId, kind = 'story_write', status = 'waiting_author', phase = 'pending_selection') {
  return {
    kind, requestId, projectId: 'project-a', status, phase, message: null,
    execution: { execution_mode: 'interactive_bridge', agent_command: '/exact-backend-command' },
    result: null, error: null,
  }
}

test('request-keyed collection keeps multiple material tasks and patches one independently', () => {
  let tasks = putTask({}, material('r1', 'book-a'))
  tasks = putTask(tasks, material('r2', 'book-b'))
  const next = patchRequestTask(tasks, 'r1', { status: 'running' })
  assert.deepEqual(Object.keys(next), ['r1', 'r2'])
  assert.equal(next.r1.status, 'running')
  assert.equal(next.r2.status, 'waiting_author')
})

test('A busy does not block B, but the same canonical asset cannot start twice', () => {
  const tasks = { r1: material('r1', 'book-a') }
  assert.equal(startConflict(tasks, { kind: 'material_distill', assetId: 'book-b' }), null)
  assert.match(startConflict(tasks, { kind: 'material_distill', assetId: 'book-a' }), /正在学习/)
})

test('material and non-material exclusivity is preserved in both directions', () => {
  assert.match(startConflict({ r1: material('r1', 'book-a') }, { kind: 'story_write' }), /素材学习/)
  assert.match(startConflict({ r2: exclusive('r2', 'review') }, { kind: 'material_distill', assetId: 'book-b' }), /其他作者任务/)
  assert.match(startConflict({ r2: exclusive('r2', 'story_plan', 'candidate') }, { kind: 'review' }), /已有进行中的任务/)
})

test('dropping one request leaves every other request intact', () => {
  const tasks = { r1: material('r1', 'book-a'), r2: material('r2', 'book-b') }
  const next = dropTask(tasks, 'r1')
  assert.deepEqual(taskList(next).map((task) => task.requestId), ['r2'])
})

test('waiting/running HCI and backend command are request-specific', () => {
  const waiting = material('r1', 'book-a', 'waiting_author', null, '/verbatim:backend')
  assert.equal(taskStripView(waiting).stateText, '等待 Agent')
  assert.equal(waiting.execution.agent_command, '/verbatim:backend')
  assert.match(taskStripView({ ...waiting, status: 'running' }).stateText, /^Agent 正在执行/)
})

test('waiting phase keys remain request-and-phase bound', () => {
  const phase1 = exclusive('write-1', 'story_write', 'waiting_author', 'pending_selection')
  const rerender = { ...phase1 }
  const phase2 = { ...phase1, phase: 'pending_prose' }
  assert.equal(waitingPhaseKey(phase1), waitingPhaseKey(rerender))
  assert.notEqual(waitingPhaseKey(phase1), waitingPhaseKey(phase2))
})

test('layout CSS avoids page-wide blank-height floors while retaining bounded workspaces', () => {
  const styles = fs.readFileSync(path.join(src, 'styles.css'), 'utf8')
  assert.doesNotMatch(styles, /main\.workspace-shell\{min-height:/)
  assert.doesNotMatch(styles, /\.empty-state\{min-height:/)
  assert.match(styles, /\.foundation-workspace\{[^}]*height:clamp\(/)
  assert.match(styles, /\.writing-layout\{[^}]*height:clamp\(/)
  assert.match(styles, /\.materials-workflow\{[^}]*height:clamp\(/)
})

test('left Agent rail maps independent request cards and legacy bottom strip is absent', () => {
  const rail = fs.readFileSync(path.join(src, 'features', 'tasks', 'AgentTaskRail.tsx'), 'utf8')
  const shell = fs.readFileSync(path.join(src, 'layouts', 'AppShell.tsx'), 'utf8')
  const styles = fs.readFileSync(path.join(src, 'styles.css'), 'utf8')
  assert.match(rail, /tasks\.map\(\(task\)/)
  assert.match(rail, /key=\{task\.requestId\}/)
  assert.doesNotMatch(rail, /`\/gowrite:/)
  assert.match(shell, /<AgentTaskRail/)
  assert.doesNotMatch(shell, /TaskStrip/)
  assert.doesNotMatch(styles, /\.task-strip/)
})
