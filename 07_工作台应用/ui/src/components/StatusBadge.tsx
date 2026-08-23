import type { WorkStatus } from '../contracts/ui'
const labels: Record<WorkStatus, string> = { idle: '待开始', running: 'AI 正在思考', candidate: '候选', waiting_confirmation: '等待确认', accepted: '已采用', failed: '执行失败' }
export function StatusBadge({ status }: { status: WorkStatus }) { return <span className={`status status-${status}`}>{labels[status]}</span> }
