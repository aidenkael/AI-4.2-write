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
import {
  graphElements,
  replaceGraphElementData,
  storyMapStyles,
} from '../.test-build/features/storyMap/storyMapCytoscape.js'

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
  assert.deepEqual(
    graph.edges[0].fields.slice(0, 2).map((field) => [field.label, field.value]),
    [['人物 A', '林砚'], ['人物 B', '苏晚晴']],
  )
  assert.ok(!graph.edges[0].fields.some((field) => field.key === 'targets'))
  assert.equal(graph.unresolved.length, 0)
})

test('人物节点只消费精确 source_ref 头像，绝不回退姓名首字', () => {
  const data = makeData({ sections: { characters: [
    { id: 'c1', label: '林砚', source_ref: 'char:1', record: { name: '林砚', one_line_intro: '雨夜归来的医生' } },
  ], relationships: [], canon_facts: [], occurred_events: [], open_threads: [], approved_plan: [] } })
  const withoutAvatar = projectRelationshipGraph(data).nodes[0]
  assert.equal(withoutAvatar.avatarImageSrc, null)
  assert.equal('avatarText' in withoutAvatar, false)
  assert.equal(withoutAvatar.intro, '雨夜归来的医生')
  const withAvatar = projectRelationshipGraph(data, { 'char:1': 'data:image/png;base64,AA==' }).nodes[0]
  assert.equal(withAvatar.avatarImageSrc, 'data:image/png;base64,AA==')
})

test('Cytoscape 头像只为真实图像建立数据与样式，并在重置时移除旧值', () => {
  const graph = projectRelationshipGraph(makeData({ sections: {
    characters: [{ id: 'c1', label: '林砚', source_ref: 'char:1', record: { name: '林砚' } }],
    relationships: [], canon_facts: [], occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], approved_plan: [],
  } }))
  const withoutAvatar = graphElements(graph)[0].data
  assert.equal('avatar' in withoutAvatar, false)
  const withAvatar = graphElements(projectRelationshipGraph(makeData({ sections: {
    characters: [{ id: 'c1', label: '林砚', source_ref: 'char:1', record: { name: '林砚' } }],
    relationships: [], canon_facts: [], occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], approved_plan: [],
  } }), { 'char:1': 'data:image/png;base64,exact' }))[0].data
  assert.equal(withAvatar.avatar, 'data:image/png;base64,exact')
  const base = storyMapStyles.find((style) => style.selector === 'node')
  const avatarOnly = storyMapStyles.find((style) => style.selector === 'node[avatar]')
  assert.equal('background-image' in base.style, false)
  assert.equal(avatarOnly.style['background-image'], 'data(avatar)')
  const current = { avatar: 'old-image' }
  const element = {
    data(nextData) { Object.assign(current, nextData) },
    removeData(key) { delete current[key] },
  }
  replaceGraphElementData(element, withoutAvatar)
  assert.equal('avatar' in current, false)
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
  assert.ok(graph.unresolved[0].reason.includes('无法唯一对应'))
  assert.ok(graph.unresolved[1].reason.includes('缺少明确的双方人物'))
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
