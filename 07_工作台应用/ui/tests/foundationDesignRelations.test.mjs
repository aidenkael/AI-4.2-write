import assert from 'node:assert/strict'
import test from 'node:test'
import {
  fdKeyTitles,
  fdRefTitles,
  fdRelationRows,
  fdRelationRowText,
  fdSelectedRelationPayload,
  RELATION_KIND_LABELS,
} from '../.test-build/features/foundation/foundationDesignRelations.js'

const proposal = {
  characters: [{ candidate_key: 'char_local_1', title: '林渊', material_state: 'future' }],
  organizations: [{ candidate_key: 'org_local_1', title: '玄天宗', material_state: 'future' }],
  systems: [{ candidate_key: 'sys_local_1', title: '玄灵境界', material_state: 'future' }],
  story_lines: [{ candidate_key: 'line_local_1', title: '主线一', material_state: 'future' }],
  domain_relations: [
    { relation_kind: 'character_affiliated_with_organization', source_key: 'char_local_1', target_key: 'org_local_1' },
    { relation_kind: 'character_uses_system', source_key: 'char_local_1', target_key: 'sys_local_1' },
    { relation_kind: 'storyline_involves_character', source_key: 'line_local_1', target_key: 'char_local_1' },
    { relation_kind: 'foreshadowing_related_to', source_key: 'ghost_key', target_key: 'org_local_1' },
    { relation_kind: 'mystery_information_related_to', source_ref: 'gw_existing_1', target_key: 'org_local_1' },
  ],
}

const projectData = {
  sections: {
    characters: [{ id: 'gw_existing_1', label: '既有悬念', source_ref: 'gw_existing_1' }],
    organizations: [], relationships: [], canon_facts: [], locations: [], systems: [],
    occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], mystery_information: [], approved_plan: [],
  },
}

test('relation rows render author-readable source — 关系标签 → target', () => {
  const rows = fdRelationRows(proposal.domain_relations, fdKeyTitles(proposal), fdRefTitles(projectData))
  assert.equal(rows.length, 5)
  assert.equal(fdRelationRowText(rows[0]), '林渊 — 所属组织 → 玄天宗')
  assert.equal(fdRelationRowText(rows[1]), '林渊 — 关联体系 → 玄灵境界')
  assert.equal(fdRelationRowText(rows[2]), '主线一 — 涉及人物 → 林渊')
  // 显式 ref 端点用既有记录标签解析
  assert.equal(fdRelationRowText(rows[4]), '既有悬念 — 相关对象 → 玄天宗')
})

test('unresolvable endpoints stay honest and never expose keys/refs/kinds', () => {
  const rows = fdRelationRows(proposal.domain_relations, fdKeyTitles(proposal), fdRefTitles(projectData))
  assert.equal(fdRelationRowText(rows[3]), null)
  for (const row of rows) {
    const text = fdRelationRowText(row)
    if (text === null) continue
    assert.ok(!text.includes('_local_'), '行文本绝不暴露候选键')
    assert.ok(!text.includes('gw_'), '行文本绝不暴露 ref')
    assert.ok(!Object.keys(RELATION_KIND_LABELS).some((kind) => text.includes(kind)), '行文本绝不暴露内部类型名')
  }
})

test('selected/unselected payload projection keeps only key/ref identity', () => {
  const rows = fdRelationRows(proposal.domain_relations, fdKeyTitles(proposal), fdRefTitles(projectData))
  const selections = rows.map((row, index) => ({ include: index < 3, row }))
  const payload = fdSelectedRelationPayload(selections)
  assert.equal(payload.length, 3)
  assert.deepEqual(payload[0], {
    relation_kind: 'character_affiliated_with_organization',
    source_key: 'char_local_1', target_key: 'org_local_1',
  })
  assert.deepEqual(payload[2], {
    relation_kind: 'storyline_involves_character',
    source_key: 'line_local_1', target_key: 'char_local_1',
  })
  // 未选关系不进入确认载荷
  assert.ok(!payload.some((item) => item.relation_kind === 'foreshadowing_related_to'))
  assert.ok(!payload.some((item) => item.relation_kind === 'mystery_information_related_to'))
})

test('explicit ref payload keeps source_ref without inventing keys', () => {
  const rows = fdRelationRows(proposal.domain_relations, fdKeyTitles(proposal), fdRefTitles(projectData))
  const payload = fdSelectedRelationPayload([{ include: true, row: rows[4] }])
  assert.deepEqual(payload, [{
    relation_kind: 'mystery_information_related_to',
    source_ref: 'gw_existing_1', target_key: 'org_local_1',
  }])
})
