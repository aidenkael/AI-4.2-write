import test from 'node:test'
import assert from 'node:assert/strict'
import {
  authorSourceLabel,
  authorStatusLabel,
  compactCharacter,
  describeAuthorRecord,
} from '../.test-build/features/presentation/authorPresentation.js'
import {
  isCurrentProjectResult,
  settlementFollowUp,
} from '../.test-build/features/projectData/mutationSettlement.js'
import {
  CHARACTER_EDITOR_FIELDS,
  splitEditorData,
} from '../.test-build/features/foundation/recordEditors.js'

const entry = {
  id: 'c1', label: '林澈', source_ref: 'gw2_obj_1', source_kind: 'author_workspace', status: 'current', editable: true,
  record: {
    one_line_intro: '谨慎的调查者', role_identity: '主角', current_state: '受伤',
    aliases: ['阿澈', '小林'], behavior_anchors: ['先观察', '再行动'],
    custom_lucky_token_name: '旧硬币', source_ref: 'internal', request_id: 'req', model_rev: 4,
    planning_source_ref: 'plan:1', structured_internal: { ref: 'x' }, notes: '',
  },
}

test('共享作者呈现隐藏内部元数据但保留作者自定义字段', () => {
  const fields = describeAuthorRecord(entry)
  const keys = fields.map((field) => field.key)
  assert.ok(!keys.includes('source_ref') && !keys.includes('request_id') && !keys.includes('model_rev'))
  assert.ok(!keys.includes('structured_internal'))
  assert.equal(fields.find((field) => field.key === 'custom_lucky_token_name')?.value, '旧硬币')
})

test('当前/规划与来源只用作者语言', () => {
  assert.equal(authorStatusLabel('current'), '当前')
  assert.equal(authorStatusLabel('future'), '规划中')
  assert.equal(authorSourceLabel('production_story_state'), '来自已采用正文')
  assert.equal(authorSourceLabel('approved_plan'), '来自已确认规划')
  assert.equal(authorSourceLabel('author_workspace'), '作者设定')
})

test('人物详情稳定排序且图节点只投影紧凑身份', () => {
  const compact = compactCharacter(entry)
  assert.equal(compact.name, '林澈')
  assert.equal(compact.intro, '谨慎的调查者')
  assert.equal(compact.role, '主角')
  assert.deepEqual(compact.details.slice(0, 3).map((field) => field.key), ['one_line_intro', 'role_identity', 'current_state'])
  assert.ok(compact.hoverFields.length <= 4)
})

test('共享编辑器保留隐藏持久化数据且不把它变成自定义字段', () => {
  const split = splitEditorData(entry, CHARACTER_EDITOR_FIELDS)
  assert.equal(split.preserved.planning_source_ref, 'plan:1')
  assert.deepEqual(split.preserved.structured_internal, { ref: 'x' })
  assert.equal(split.values.aliases, '阿澈、小林')
  assert.equal(split.values.behavior_anchors, '先观察、再行动')
  assert.equal(split.knownListFields.has('aliases'), true)
  assert.equal(split.knownListFields.has('behavior_anchors'), true)
  assert.ok(!split.custom.some((field) => field.key === 'planning_source_ref'))
  assert.ok(split.custom.some((field) => field.key === 'custom_lucky_token_name'))
})

test('mutation follow-up only follows an already-started semantic settlement', () => {
  assert.deepEqual(settlementFollowUp({
    change: { change_id: 'c1', requires_semantic: true },
    settlement_request: { request_started: true, request_id: 'r1', message: '正在同步' },
  }), { requestId: 'r1', changeId: 'c1', message: '正在同步' })
  assert.equal(settlementFollowUp({
    change: { change_id: 'c2', requires_semantic: false },
    settlement_request: { request_started: false },
  }), null)
})

test('项目切换后拒绝旧 settlement 完成结果', () => {
  assert.equal(isCurrentProjectResult('p1', 'p1'), true)
  assert.equal(isCurrentProjectResult('p1', 'p2'), false)
})
