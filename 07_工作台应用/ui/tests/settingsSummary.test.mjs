/**
 * settingsSummary 纯函数测试：交互摘要绝不包含 Direct 模型。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { savedExecutionSummary } from '../.test-build/features/settings/settingsSummary.js'

const agentName = (id) => (id === 'qoder' ? 'Qoder' : id)

test('direct summary 可显示保存的精确 Direct 模型', () => {
  const text = savedExecutionSummary({
    default_execution_mode: 'direct',
    interactive_agent: 'qoder',
    direct_agent: 'deepseek_harness',
    direct_model: 'deepseek-v4',
    direct_custom_model: null,
  }, agentName)
  assert.ok(text.includes('直接执行'))
  assert.ok(text.includes('deepseek_harness'))
  assert.ok(text.includes('deepseek-v4'))
})

test('interactive summary 只显示 Interactive Agent，绝不拼入 Direct 模型', () => {
  const text = savedExecutionSummary({
    default_execution_mode: 'interactive_bridge',
    interactive_agent: 'qoder',
    direct_agent: 'deepseek_harness',
    direct_model: 'deepseek-v4',
    direct_custom_model: null,
  }, agentName)
  assert.ok(text.includes('交互桥'))
  assert.ok(text.includes('Qoder'))
  assert.ok(!text.includes('deepseek-v4'), 'Direct 模型不得污染交互摘要')
  assert.ok(!text.includes('deepseek_harness'))
  assert.ok(text.includes('模型未验证'), '交互模型未经机械验证：明确标注未知')
})

test('interactive summary 也不得使用 direct_custom_model', () => {
  const text = savedExecutionSummary({
    default_execution_mode: 'interactive_bridge',
    interactive_agent: 'qoder',
    direct_agent: 'deepseek_harness',
    direct_model: null,
    direct_custom_model: 'harness:deepseek:custom-1',
  }, agentName)
  assert.ok(!text.includes('custom-1'))
})
