import assert from 'node:assert/strict'
import test from 'node:test'
import {
  minimalProjectDataPassesContract,
  missingRetiredSurfaceIsRejected,
  retiredRecordsRenderWithRestoreAction,
} from '../.test-build/tests/projectPageRuntimeHarness.js'

test('minimal ProjectData with retired surface passes the shared contract', () => {
  assert.equal(minimalProjectDataPassesContract(), true)
})

test('ProjectData without the retired surface is rejected at the shared boundary', () => {
  assert.equal(missingRetiredSurfaceIsRejected(), true)
})

test('retired records render in the 已退役 area with a 恢复 action', async () => {
  assert.equal(await retiredRecordsRenderWithRestoreAction(), true)
})
