import assert from 'node:assert/strict'
import test from 'node:test'
import {
  FOUNDATION_FIELD_PRESENTATION,
  advancedValueCount,
  fieldsForCategory,
  primaryFoundationSections,
  sectionFields,
} from '../.test-build/features/foundation/fieldPresentation.js'
import { splitEditorData } from '../.test-build/features/foundation/recordEditors.js'

const categories = [
  'character', 'relationship', 'world_setting', 'location', 'organization_force',
  'system', 'story_line', 'promise_foreshadowing', 'mystery_information',
]

test('every current Foundation category has a sparse core and advanced presentation', () => {
  assert.deepEqual(Object.keys(FOUNDATION_FIELD_PRESENTATION), categories)
  for (const category of categories) {
    assert.ok(sectionFields(category, 'core').length > 0, `${category} needs core fields`)
    assert.ok(sectionFields(category, 'advanced').length > 0, `${category} needs advanced fields`)
  }
  assert.deepEqual(sectionFields('character', 'core').map((field) => field.key), [
    'one_line_intro', 'role_identity', 'goal_desire',
  ])
  assert.deepEqual(sectionFields('relationship', 'core').map((field) => field.key), [
    'description', 'current_state',
  ])
})

test('advanced indicator counts meaningful known and custom values only', () => {
  assert.equal(advancedValueCount('character', {
    one_line_intro: '核心字段不计数', notes: '已有备注', aliases: '', current_level: '第三阶',
  }, [
    { key: '自定义', value: '保留' }, { key: '', value: '无字段名' }, { key: '空值', value: '  ' },
  ]), 3)
})

test('hidden advanced and internal values survive split without blank-field creation', () => {
  const entry = {
    id: 'c1', label: '人物甲', source_ref: 'gw_char_1', source_kind: 'author_workspace',
    status: 'current', editable: true, category: 'character',
    record: { name: '人物甲', one_line_intro: '侦查者', notes: '不可丢', custom_fact: '保留', source_ref: 'internal-ref' },
  }
  const tuples = fieldsForCategory('character').map((field) => [field.key, field.label])
  const split = splitEditorData(entry, tuples)
  assert.equal(split.values.notes, '不可丢')
  assert.deepEqual(split.custom, [{ key: 'custom_fact', value: '保留', isList: false }])
  assert.equal(split.preserved.source_ref, 'internal-ref')
  assert.equal(split.values.aliases, '')
})

test('inactive optional areas stay secondary while real records remain primary', () => {
  const inactive = primaryFoundationSections([], { systems: 0, mystery_information: 0 })
  assert.equal(inactive.primary.includes('systems'), false)
  assert.equal(inactive.primary.includes('mystery_information'), false)
  assert.deepEqual(inactive.optional, ['systems', 'mystery_information'])
  for (const core of ['characters', 'relationships', 'canon_facts', 'locations', 'organizations', 'storylines', 'foreshadowing']) {
    assert.ok(inactive.primary.includes(core))
  }

  const staleProfile = primaryFoundationSections([], { systems: 1, mystery_information: 2 })
  assert.ok(staleProfile.primary.includes('systems'))
  assert.ok(staleProfile.primary.includes('mystery_information'))

  const configured = primaryFoundationSections(['power_progression', 'mystery_information'], {})
  assert.ok(configured.primary.includes('systems'))
  assert.ok(configured.primary.includes('mystery_information'))
})

test('internal metadata is never declared as an author field', () => {
  const internal = new Set(['id', 'ref', 'source_ref', 'source_kind', 'model_rev', 'state_rev', 'authority', 'provenance'])
  for (const field of Object.values(FOUNDATION_FIELD_PRESENTATION).flat()) {
    assert.equal(internal.has(field.key), false, field.key)
  }
})
