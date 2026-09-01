import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeChapterForeshadowing } from '../.test-build/features/planning/planningFields.js'

test('chapter foreshadowing reads the legacy alias but saves through one canonical field', () => {
  assert.deepEqual(normalizeChapterForeshadowing({ foreshadowing_setup_payoff: ['旧线索'] }), ['旧线索'])
  assert.deepEqual(
    normalizeChapterForeshadowing({ foreshadowing: ['当前线索'], foreshadowing_setup_payoff: ['旧线索'] }),
    ['当前线索'],
  )
})
