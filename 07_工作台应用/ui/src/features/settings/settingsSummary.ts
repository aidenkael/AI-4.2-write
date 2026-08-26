/**
 * 设置"已保存配置"摘要（纯函数，可被 node:test 直接测试）。
 *
 * 真相规则：
 * - Direct：可以展示保存的精确 Direct 模型；
 * - Interactive：只展示已保存的 Interactive Agent；绝不把 Direct 模型拼进
 *   交互配置；交互桥模型只有 Go Write 从实际执行机械验证后才可知，
 *   保存摘要一律标注"模型未验证"（不编造模型身份）。
 */

export interface SavedExecutionLike {
  default_execution_mode: string
  interactive_agent: string
  direct_agent: string
  direct_model: string | null
  direct_custom_model: string | null
}

export function savedExecutionSummary(
  saved: SavedExecutionLike,
  agentName: (agentId: string) => string,
): string {
  if (saved.default_execution_mode === 'direct') {
    const model = saved.direct_model ?? saved.direct_custom_model
    return `直接执行 · ${agentName(saved.direct_agent)}${model ? ` · ${model}` : ''}`
  }
  return `交互桥 · ${agentName(saved.interactive_agent)} · 模型未验证`
}
