import { Copy, ExternalLink, X } from 'lucide-react'
import { taskStripView, type AuthorTask } from './taskModel'

interface AgentTaskRailViewProps {
  tasks: AuthorTask[]
  onCopy(command: string): void
  onFocus(command: string): void
  onCancel(requestId: string): void
  onNavigate(requestId: string): void
}

/** Pure task-rail view kept separate so waiting/running author actions are render-tested. */
export function AgentTaskRailView({ tasks, onCopy, onFocus, onCancel, onNavigate }: AgentTaskRailViewProps) {
  return <aside className="agent-task-rail" aria-label="Agent 任务">
    <h2>Agent 任务</h2>
    {tasks.length === 0
      ? <p className="agent-rail-empty">当前没有进行中的任务</p>
      : <div className="agent-task-list">{tasks.map((task) => {
          const view = taskStripView(task)
          const waiting = task.status === 'waiting_author'
          const command = task.execution?.agent_command
          const targetLabel = typeof task.meta?.target_label === 'string' ? task.meta.target_label : null
          return <article className="agent-task-card" key={task.requestId} data-request-id={task.requestId}>
            <strong>{view.label}</strong>
            {targetLabel ? <small className="agent-task-target">{targetLabel}</small> : null}
            <span>{view.stateText}</span>
            {waiting && task.message && task.message !== view.stateText ? <small>{task.message}</small> : null}
            {waiting && command
              ? <div className="agent-task-command-row">
                  <code className="agent-task-command">{command}</code>
                  <button aria-label={`复制 ${command}`} onClick={() => onCopy(command)}><Copy size={15}/>复制</button>
                </div>
              : null}
            <div className="agent-task-actions">
              {waiting && command
                ? <button className="secondary" onClick={() => onFocus(command)}><ExternalLink size={14}/>前往 Qoder</button>
                : <button className="secondary" onClick={() => onNavigate(task.requestId)}>{view.primaryLabel}</button>}
              {view.canCancel
                ? <button title="取消任务" aria-label="取消任务" onClick={() => onCancel(task.requestId)}><X size={15}/></button>
                : null}
            </div>
          </article>
        })}</div>}
  </aside>
}
