import { focusQoder } from '../../bridge/client'
import { useAuthorTask } from './AuthorTaskCoordinator'
import { taskList } from './coordinatorModel'
import { AgentTaskRailView } from './AgentTaskRailView'

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

  return <AgentTaskRailView
    tasks={tasks}
    onCopy={(command) => { void copyCommand(command) }}
    onFocus={(command) => { void focus(command) }}
    onCancel={(requestId) => { void cancel(requestId) }}
    onNavigate={navigateToTask}
  />
}
