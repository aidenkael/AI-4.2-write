import type { ReactNode } from 'react'

export interface ExecutionFacts {
  execution_mode?: string | null
  agent_id?: string | null
  model?: string | null
}

const modeLabel = (mode: string | null | undefined) =>
  mode === 'direct' ? '直接模式' : mode === 'interactive_bridge' ? '交互桥 /gowrite' : mode ?? ''

/**
 * 紧凑“本次执行”摘要行：只渲染后端真实返回的非机密执行元数据，
 * 绝不编造执行状态；缺少信息时返回 null。
 */
export function ExecutionSummary({ execution }: { execution: ExecutionFacts | null | undefined }): ReactNode {
  if (!execution) return null
  const mode = modeLabel(execution.execution_mode)
  const agent = execution.agent_id
  const model = execution.model
  const parts: string[] = []
  if (mode) parts.push(mode)
  if (agent) parts.push(agent)
  if (model) parts.push(model)
  if (parts.length === 0) return null
  return <p className="muted-note execution-summary">本次执行：{parts.join(' · ')}</p>
}
