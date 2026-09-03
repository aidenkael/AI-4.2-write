import assert from 'node:assert/strict'
import test from 'node:test'
import {
  errorBoundaryKeepsProjectNavigation,
  invalidProjectDataIsRejected,
  mountAllProjectPages,
  storyMapDirectCreateUsesSharedEditors,
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

test('Story Map direct create mounts the shared character and relationship editors', async () => {
  assert.equal(await storyMapDirectCreateUsesSharedEditors(), true)
})
