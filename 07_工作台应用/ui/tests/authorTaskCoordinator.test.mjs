import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { create } from 'react-test-renderer'
import {
  dropTask, patchRequestTask, putTask, resolveTaskStartFacts, startConflict, taskList, waitingPhaseKey,
} from '../.test-build/features/tasks/coordinatorModel.js'
import { AgentTaskRailView } from '../.test-build/features/tasks/AgentTaskRailView.js'
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

test('material start trusts backend execution facts when prepare omits them', () => {
  const waiting = resolveTaskStartFacts('material_distill', {}, {
    execution_mode: 'interactive_bridge',
    execution_phase: 'waiting_agent',
    agent_command: '/gowrite:2',
    agent_id: 'qoder',
  })
  assert.equal(waiting.status, 'waiting_author')
  assert.equal(waiting.execution.agent_command, '/gowrite:2')
  assert.equal(waiting.execution.execution_mode, 'interactive_bridge')

  const running = resolveTaskStartFacts('material_distill', {}, {
    execution_mode: 'interactive_bridge',
    execution_phase: 'running',
    agent_command: '/gowrite:2',
  })
  assert.equal(running.status, 'running')
})

test('AgentTaskRail waiting material renders exact command and author-readable actions only while waiting', () => {
  const waiting = material('r1', 'book-a', 'waiting_author', null, '/gowrite:2')
  waiting.meta.target_label = '将夜'
  const copied = []
  const focused = []
  const renderer = create(React.createElement(AgentTaskRailView, {
    tasks: [waiting],
    onCopy: (command) => copied.push(command),
    onFocus: (command) => focused.push(command),
    onCancel: () => {},
    onNavigate: () => {},
  }))
  const waitingText = JSON.stringify(renderer.toJSON())
  assert.match(waitingText, /素材学习/)
  assert.match(waitingText, /将夜/)
  assert.match(waitingText, /\/gowrite:2/)
  assert.match(waitingText, /复制/)
  assert.match(waitingText, /前往 Qoder/)
  const buttons = renderer.root.findAllByType('button')
  buttons.find((button) => String(button.props['aria-label'] ?? '').startsWith('复制 ')).props.onClick()
  buttons.find((button) => button.children.some((child) => child === '前往 Qoder')).props.onClick()
  assert.deepEqual(copied, ['/gowrite:2'])
  assert.deepEqual(focused, ['/gowrite:2'])

  renderer.update(React.createElement(AgentTaskRailView, {
    tasks: [{ ...waiting, status: 'running' }],
    onCopy: () => {}, onFocus: () => {}, onCancel: () => {}, onNavigate: () => {},
  }))
  const runningText = JSON.stringify(renderer.toJSON())
  assert.doesNotMatch(runningText, /\/gowrite:2/)
  assert.doesNotMatch(runningText, /前往 Qoder/)
  renderer.unmount()
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

test('1920px desktop workspace has 24px outer gutters and no legacy outer width cap', () => {
  const styles = fs.readFileSync(path.join(src, 'styles.css'), 'utf8')
  assert.doesNotMatch(styles, /--workspace-(?:max|content-max)/)
  assert.match(styles, /\.app-shell>main\.workspace-shell\{[^}]*width:100%;[^}]*max-width:none;[^}]*margin:0;[^}]*padding:18px 24px 42px/)
  assert.match(styles, /grid-template-columns:var\(--agent-rail-width\) minmax\(0,1fr\)/)
  assert.match(styles, /\.workspace-content\{[^}]*min-width:0;[^}]*width:100%;[^}]*max-width:none/)
  assert.match(styles, /\.page\{[^}]*width:100%;[^}]*max-width:none;[^}]*margin:0/)
  assert.match(styles, /\.project-content\{[^}]*width:100%;[^}]*max-width:none;[^}]*margin:0/)
  assert.doesNotMatch(styles, /\.(?:overview-page|foundation-page|planning-page|review-page)\{[^}]*max-width:/)
  const viewport = 1920
  const gutter = 24
  const rail = 260
  const gap = 18
  assert.equal(viewport - (2 * gutter) - rail - gap, 1594)
})

test('left Agent rail maps independent request cards and legacy bottom strip is absent', () => {
  const rail = fs.readFileSync(path.join(src, 'features', 'tasks', 'AgentTaskRail.tsx'), 'utf8')
  const railView = fs.readFileSync(path.join(src, 'features', 'tasks', 'AgentTaskRailView.tsx'), 'utf8')
  const shell = fs.readFileSync(path.join(src, 'layouts', 'AppShell.tsx'), 'utf8')
  const styles = fs.readFileSync(path.join(src, 'styles.css'), 'utf8')
  assert.match(railView, /tasks\.map\(\(task\)/)
  assert.match(railView, /key=\{task\.requestId\}/)
  assert.doesNotMatch(`${rail}\n${railView}`, /`\/gowrite:/)
  assert.match(shell, /<AgentTaskRail/)
  assert.doesNotMatch(shell, /TaskStrip/)
  assert.doesNotMatch(styles, /\.task-strip/)
  const coordinator = fs.readFileSync(path.join(src, 'features', 'tasks', 'AuthorTaskCoordinator.tsx'), 'utf8')
  assert.match(coordinator, /已复制 \$\{command\}，请在 Qoder 中执行。/)
  assert.match(coordinator, /自动复制失败，请点击复制/)
})
