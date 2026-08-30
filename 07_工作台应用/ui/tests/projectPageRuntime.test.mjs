import assert from 'node:assert/strict'
import test from 'node:test'
import {
  errorBoundaryKeepsProjectNavigation,
  invalidProjectDataIsRejected,
  mountAllProjectPages,
} from '../.test-build/tests/projectPageRuntimeHarness.js'

test('all six project pages mount with the current minimal ProjectData contract', async () => {
  await mountAllProjectPages()
})

test('malformed non-null ProjectData is rejected before page render', () => {
  assert.equal(invalidProjectDataIsRejected(), true)
})

test('project page error boundary preserves project navigation', async () => {
  assert.equal(await errorBoundaryKeepsProjectNavigation(), true)
})
