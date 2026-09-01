import assert from 'node:assert/strict'
import test from 'node:test'
import {
  RELATION_SPECS_BY_SOURCE_CATEGORY,
  displayLabel,
  initializeRelationSelections,
  legacyFieldsToStrip,
  relationOptions,
  relationSelections,
  resolveLegacyTitles,
  stripLegacyRelationFields,
} from '../.test-build/features/foundation/relationSelectors.js'

const entry = (sourceRef, label, status = 'current') => ({
  id: sourceRef, label, record: { name: label }, source_ref: sourceRef,
  source_kind: 'author_workspace', category: null, status, editable: true,
})

const emptySections = {
  characters: [], relationships: [], canon_facts: [], locations: [], organizations: [], systems: [],
  occurred_events: [], open_threads: [], foreshadowing: [], storylines: [], mystery_information: [], approved_plan: [],
}

function dataWith(overrides) {
  return {
    project_id: 'proj', name: '测试作品', state_rev: 0, model_rev: 3, last_authority_source: null,
    work_direction: '', reader_promise: '', settlement: { status: 'synchronized', pending_count: 0, failed_count: 0, changes: [] },
    state_refresh: { status: 'synchronized', pending_change_count: 0, awaiting_confirmation_count: 0, refresh_id: null, worker_active: false, summary: null, error: null },
    story_bible_profile: { genre_tags: [], narrative_mode: null, active_modules: [], field_config: {} },
    length_plan: { total_target_words: null, actual_total_words: 0, stages: [], chapters: [] },
    chapters: [], planning_impact_candidates: [], explicit_dependencies: [],
    retired: { foundation: [], relationships: [] },
    sections: { ...emptySections, ...overrides.sections },
    ...overrides,
  }
}

test('relation targets come only from real ProjectData sections', () => {
  const data = dataWith({
    sections: {
      organizations: [entry('gw_org_1', '玄天宗'), entry('gw_org_2', '北境盟', 'future')],
      systems: [entry('gw_sys_1', '玄灵境界')],
    },
  })
  const orgOptions = relationOptions(data, ['organization_force'])
  assert.deepEqual(orgOptions.map((option) => option.ref), ['gw_org_1', 'gw_org_2'])
  assert.equal(orgOptions[1].status, 'future')
  const systemOptions = relationOptions(data, ['system'])
  assert.deepEqual(systemOptions.map((option) => option.ref), ['gw_sys_1'])
  assert.deepEqual(relationOptions(null, ['system']), [])
})

test('legacy exact unique titles preselect; ambiguous/unmatched never resolve', () => {
  const options = [
    { ref: 'gw_org_1', label: '玄天宗', category: 'organization_force', status: 'current' },
    { ref: 'gw_org_2', label: '同名门', category: 'organization_force', status: 'current' },
    { ref: 'gw_org_3', label: '同名门', category: 'organization_force', status: 'current' },
  ]
  const unique = resolveLegacyTitles(['玄天宗'], options)
  assert.deepEqual(unique, { refs: ['gw_org_1'], unresolved: [] })
  const ambiguous = resolveLegacyTitles(['同名门'], options)
  assert.deepEqual(ambiguous, { refs: [], unresolved: ['同名门'] })
  const unmatched = resolveLegacyTitles(['不存在的组织'], options)
  assert.deepEqual(unmatched, { refs: [], unresolved: ['不存在的组织'] })
})

test('initialization prefers canonical relations; legacy only preselects when fully unique', () => {
  const sections = {
    organizations: [entry('gw_org_1', '玄天宗')],
    characters: [entry('gw_char_1', '林渊')],
  }
  const canonical = dataWith({
    sections,
    explicit_dependencies: [{
      ref: 'gw_edge_1', relation_kind: 'character_affiliated_with_organization', title: '所属组织',
      material_state: 'current', source_ref: 'gw_char_1', source_title: '林渊', source_category: 'character',
      target_ref: 'gw_org_1', target_title: '玄天宗', target_category: 'organization_force',
    }],
  })
  const withCanonical = initializeRelationSelections({
    category: 'character', sourceRef: 'gw_char_1',
    record: { faction_org: '别的文本' }, data: canonical,
  })
  // 规范化关系优先；未规范化的遗留文本仍以作者可读提示如实呈现，不静默丢弃。
  assert.deepEqual(withCanonical.selections.character_affiliated_with_organization, ['gw_org_1'])
  assert.equal(withCanonical.hints.length, 1)
  assert.ok(withCanonical.hints[0].text.includes('别的文本'))

  const noCanonical = dataWith({ sections })
  const legacyUnique = initializeRelationSelections({
    category: 'character', sourceRef: 'gw_char_1',
    record: { faction_org: '玄天宗' }, data: noCanonical,
  })
  assert.deepEqual(legacyUnique.selections.character_affiliated_with_organization, ['gw_org_1'])
  assert.deepEqual(legacyUnique.hints, [])

  const legacyAmbiguous = initializeRelationSelections({
    category: 'character', sourceRef: 'gw_char_1',
    record: { faction_org: '不存在、玄天宗' }, data: noCanonical,
  })
  assert.deepEqual(legacyAmbiguous.selections.character_affiliated_with_organization, [])
  assert.equal(legacyAmbiguous.hints.length, 1)
  assert.ok(legacyAmbiguous.hints[0].text.includes('不存在、玄天宗'))
})

test('after explicit canonical selection the duplicate legacy text stops being written', () => {
  const selections = { character_affiliated_with_organization: ['gw_org_1'], character_uses_system: [] }
  assert.deepEqual(legacyFieldsToStrip('character', selections), ['faction_org'])
  const stripped = stripLegacyRelationFields(
    { faction_org: '玄天宗', power_rank: '三阶', notes: '保留' },
    legacyFieldsToStrip('character', selections),
  )
  assert.deepEqual(stripped, { power_rank: '三阶', notes: '保留' })
  // 无规范化选择时不删除遗留文本
  assert.deepEqual(legacyFieldsToStrip('character', { character_affiliated_with_organization: [] }), [])
  // 故事线双字段映射
  const storylineSelections = {
    storyline_involves_character: ['gw_char_1'],
    storyline_involves_organization: [],
    storyline_involves_location: ['gw_loc_1'],
  }
  assert.deepEqual(
    legacyFieldsToStrip('story_line', storylineSelections).sort(),
    ['participating_characters', 'related_organizations_locations'],
  )
})

test('author-facing labels never expose raw refs', () => {
  assert.equal(displayLabel({ ref: 'gw_org_1', label: '玄天宗', category: 'organization_force', status: 'current' }), '玄天宗')
  assert.equal(displayLabel({ ref: 'gw_org_1', label: '  ', category: 'organization_force', status: 'current' }), '（未命名记录）')
  const selections = relationSelections({ character_uses_system: ['gw_sys_1'] })
  assert.deepEqual(selections, [{ relation_kind: 'character_uses_system', target_ref: 'gw_sys_1' }])
})

test('approved relation kinds match the backend domain spec exactly', () => {
  const kinds = Object.values(RELATION_SPECS_BY_SOURCE_CATEGORY).flat().map((spec) => spec.relation_kind).sort()
  assert.deepEqual(kinds, [
    'character_affiliated_with_organization',
    'character_uses_system',
    'foreshadowing_related_to',
    'mystery_information_related_to',
    'storyline_involves_character',
    'storyline_involves_location',
    'storyline_involves_organization',
  ])
})
