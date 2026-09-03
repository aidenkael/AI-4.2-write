import assert from 'node:assert/strict'
import test from 'node:test'
import {
  acceptsProjectDataResponse,
  projectDataLoadMode,
} from '../.test-build/features/projectData/projectDataLoadState.js'

test('same-project mutation reload keeps existing data mounted', () => {
  assert.equal(projectDataLoadMode('project-a', 'project-a'), 'refresh')
  assert.equal(projectDataLoadMode(null, 'project-a'), 'initial')
  assert.equal(projectDataLoadMode('project-a', 'project-b'), 'initial')
})

test('project switch remains a true load and stale results are rejected', () => {
  assert.equal(acceptsProjectDataResponse('project-b', 'project-a', 'project-a'), false)
  assert.equal(acceptsProjectDataResponse('project-b', 'project-b', 'project-a'), false)
  assert.equal(acceptsProjectDataResponse('project-b', 'project-b', 'project-b'), true)
})
