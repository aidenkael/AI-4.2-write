/**
 * storyMapModel 纯函数测试（node:test；编译产物来自 tsconfig.tests.json）。
 * 字段形状取自仓库真实 Story State 合同（backend/operations/test_project_data.py 同款）：
 * character {id,name,note,authority} / relationship {id,description,targets,authority}
 * / event {id,description,authority}。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  projectRelationshipGraph,
  projectTimeEvents,
  projectOpenThreads,
  describeRecord,
} from '../.test-build/features/storyMap/storyMapModel.js'

const AUTH = 'author_decision:test'

function makeData(overrides = {}) {
  return {
    project_id: 'p1',
    name: '测试作品',
    state_rev: 1,
    last_authority_source: AUTH,
    work_direction: '',
    reader_promise: '',
    sections: {
      characters: [],
      relationships: [],
      canon_facts: [],
      occurred_events: [],
      open_threads: [],
      foreshadowing: [],
      storylines: [],
      approved_plan: [],
    },
    ...overrides,
  }
}

test('显式人物 + 显式有效关系 => 节点 + 边', () => {
  const data = makeData({
    sections: {
      characters: [
        { id: 'c1', label: '林砚', record: { id: 'c1', name: '林砚', note: '主角', authority: AUTH } },
        { id: 'c2', label: '苏晚晴', record: { id: 'c2', name: '苏晚晴', note: '协助者', authority: AUTH } },
      ],
      relationships: [
        { id: 'r1', label: '林砚与苏晚晴是旧识', record: { id: 'r1', description: '林砚与苏晚晴是旧识', targets: ['c1', 'c2'], authority: AUTH } },
      ],
      canon_facts: [], occurred_events: [], open_threads: [], approved_plan: [],
    },
  })
  const graph = projectRelationshipGraph(data)
  assert.equal(graph.nodes.length, 2)
  assert.equal(graph.edges.length, 1)
  assert.deepEqual([graph.edges[0].source, graph.edges[0].target], ['c1', 'c2'])
  assert.equal(graph.unresolved.length, 0)
})

test('关系端点无法解析 => 不臆造边 + unresolved 条目', () => {
  const data = makeData({
    sections: {
      characters: [{ id: 'c1', label: '林砚', record: { id: 'c1', name: '林砚', authority: AUTH } }],
      relationships: [
        { id: 'r1', label: '林砚与某未知人物对立', record: { id: 'r1', description: '林砚与某未知人物对立', targets: ['c1', 'c9'], authority: AUTH } },
        { id: 'r2', label: '无端点字段的关系', record: { id: 'r2', relation: '姐妹', status: '冲突', authority: AUTH } },
      ],
      canon_facts: [], occurred_events: [], open_threads: [], approved_plan: [],
    },
  })
  const graph = projectRelationshipGraph(data)
  assert.equal(graph.edges.length, 0, '不得臆造边')
  assert.equal(graph.unresolved.length, 2)
  assert.ok(graph.unresolved[0].reason.includes('端点无法对应'))
  assert.ok(graph.unresolved[1].reason.includes('没有显式两端字段'))
})

test('重复关系记录只呈现一次渲染身份', () => {
  const rel = { id: 'r1', description: '林砚与苏晚晴是旧识', targets: ['c1', 'c2'], authority: AUTH }
  const data = makeData({
    sections: {
      characters: [
        { id: 'c1', label: '林砚', record: { id: 'c1', name: '林砚', authority: AUTH } },
        { id: 'c2', label: '苏晚晴', record: { id: 'c2', name: '苏晚晴', authority: AUTH } },
      ],
      relationships: [
        { id: 'r1', label: '林砚与苏晚晴是旧识', record: rel },
        { id: 'r1', label: '林砚与苏晚晴是旧识', record: rel },
      ],
      canon_facts: [], occurred_events: [], open_threads: [], approved_plan: [],
    },
  })
  const graph = projectRelationshipGraph(data)
  assert.equal(graph.edges.length, 1)
})

test('显式时间锚点 => 时间线保留；无锚点 => 仅顺序且标注', () => {
  const data = makeData({
    sections: {
      characters: [], relationships: [], canon_facts: [],
      occurred_events: [
        { id: 'e1', label: '谈判完成', record: { id: 'e1', description: '谈判完成', time_anchor: '第三天清晨', authority: AUTH } },
        { id: 'e2', label: '收到匿名照片', record: { id: 'e2', description: '收到匿名照片', authority: AUTH } },
      ],
      open_threads: [], approved_plan: [],
    },
  })
  const model = projectTimeEvents(data)
  assert.equal(model.hasPreciseAnchors, true)
  assert.equal(model.items[0].anchor, '第三天清晨')
  assert.equal(model.items[1].anchor, null)
  assert.deepEqual(model.items.map((i) => i.order), [0, 1], '保留真实叙事顺序')
})

test('全部事件无锚点 => hasPreciseAnchors=false 且顺序保留', () => {
  const data = makeData({
    sections: {
      characters: [], relationships: [], canon_facts: [],
      occurred_events: [
        { id: 'e1', label: '事件一', record: { id: 'e1', description: '事件一', authority: AUTH } },
        { id: 'e2', label: '事件二', record: { id: 'e2', description: '事件二', authority: AUTH } },
      ],
      open_threads: [], approved_plan: [],
    },
  })
  const model = projectTimeEvents(data)
  assert.equal(model.hasPreciseAnchors, false)
  assert.deepEqual(model.items.map((i) => i.label), ['事件一', '事件二'])
})

test('空输入 => 安全空输出', () => {
  const empty = projectRelationshipGraph(makeData())
  assert.deepEqual(empty, { nodes: [], edges: [], unresolved: [] })
  assert.deepEqual(projectRelationshipGraph(null), { nodes: [], edges: [], unresolved: [] })
  assert.deepEqual(projectTimeEvents(makeData()), { items: [], hasPreciseAnchors: false })
  assert.deepEqual(projectTimeEvents(null), { items: [], hasPreciseAnchors: false })
  assert.deepEqual(projectOpenThreads(makeData()), [])
  assert.deepEqual(projectOpenThreads(null), [])
})

test('describeRecord 跳过机械键、保留真实字段', () => {
  const fields = describeRecord({
    id: 'c1',
    label: '林砚',
    record: { id: 'c1', name: '林砚', note: '主角', authority: AUTH, tags: ['医生', '雾城'] },
  })
  const keys = fields.map((f) => f.key)
  assert.ok(!keys.includes('id') && !keys.includes('authority') && !keys.includes('name'))
  assert.deepEqual(fields.find((f) => f.key === 'note'), { key: 'note', label: '备注', value: '主角' })
  assert.deepEqual(fields.find((f) => f.key === 'tags'), { key: 'tags', label: 'tags', value: '医生、雾城' })
})

test('当前与规划中的人物关系保持清晰状态并保留统一编辑源', () => {
  const data = makeData({
    sections: {
      characters: [
        { id: 'obj:1', label: '当前人物', source_ref: 'obj:1', status: 'current', editable: true, record: { name: '当前人物' } },
        { id: 'obj:2', label: '规划人物', source_ref: 'obj:2', status: 'future', editable: true, record: { name: '规划人物' } },
      ],
      relationships: [
        { id: 'edge:1', label: '未来合作', source_ref: 'edge:1', status: 'future', editable: true, record: { source: 'obj:1', target: 'obj:2' } },
      ],
      canon_facts: [], occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], approved_plan: [],
    },
  })
  const graph = projectRelationshipGraph(data)
  assert.deepEqual(graph.nodes.map((item) => item.status), ['current', 'future'])
  assert.equal(graph.edges[0].status, 'future')
  assert.equal(graph.edges[0].sourceRef, 'edge:1')
  assert.equal(graph.edges[0].editable, true)
})

test('时间事件区分已发生与规划，线索视图同时包含结构化伏笔', () => {
  const data = makeData({
    sections: {
      characters: [], relationships: [], canon_facts: [], storylines: [], approved_plan: [],
      occurred_events: [
        { id: 'e1', label: '已经发生', status: 'current', record: {} },
        { id: 'e2', label: '未来事件', status: 'future', record: { relative_duration: '一年后' } },
      ],
      open_threads: [{ id: 't1', label: '谁寄了信', status: 'current', record: {} }],
      foreshadowing: [{ id: 'f1', label: '旧信', source_ref: 'obj:f1', status: 'future', editable: true, record: { status: 'planned' } }],
    },
  })
  const timeline = projectTimeEvents(data)
  assert.deepEqual(timeline.items.map((item) => item.status), ['current', 'future'])
  const threads = projectOpenThreads(data)
  assert.deepEqual(threads.map((item) => item.kind), ['thread', 'foreshadowing'])
  assert.equal(threads[1].status, 'future')
  assert.equal(threads[1].sourceRef, 'obj:f1')
})
