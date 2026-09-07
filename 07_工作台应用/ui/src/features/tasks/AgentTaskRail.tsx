import { Copy, ExternalLink, X } from 'lucide-react'
import { focusQoder } from '../../bridge/client'
import { useAuthorTask } from './AuthorTaskCoordinator'
import { taskList } from './coordinatorModel'
import { taskStripView } from './taskModel'

async function copyCommand(command: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(command); return true } catch { /* desktop fallback */ }
  try {
    const input = document.createElement('textarea')
    input.value = command
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    const ok = document.execCommand('copy')
    input.remove()
    return ok
  } catch { return false }
}

/** Persistent rail; every action is explicitly scoped to one request_id. */
export function AgentTaskRail() {
  const { tasksByRequestId, cancel, navigateToTask } = useAuthorTask()
  const tasks = taskList(tasksByRequestId).filter((task) => task.status !== 'canceled')

  const focus = async (command: string) => {
    await copyCommand(command)
    try { await focusQoder() } catch { /* exact copied command remains usable */ }
  }

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
            <div className="agent-task-actions">
              {waiting && command
                ? <>
                    <button title={`复制 ${command}`} aria-label={`复制 ${command}`} onClick={() => void copyCommand(command)}><Copy size={15}/></button>
                    <button className="secondary" onClick={() => void focus(command)}><ExternalLink size={14}/>前往 Qoder</button>
                  </>
                : <button className="secondary" onClick={() => navigateToTask(task.requestId)}>{view.primaryLabel}</button>}
              {view.canCancel
                ? <button title="取消任务" aria-label="取消任务" onClick={() => void cancel(task.requestId)}><X size={15}/></button>
                : null}
            </div>
          </article>
        })}</div>}
  </aside>
}
