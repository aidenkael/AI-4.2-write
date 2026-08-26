/**
 * 全局运行任务条：App 级协调器任务的紧凑持久 HCI。
 *
 * 只在协调器存在任务时显示；页面切换不影响。展示：
 * - 操作标签 + 项目名（可用时）
 * - 当前真实状态（绝不伪造进度）
 * - 主动作：返回任务 / 前往 Qoder 执行 /gowrite
 * - 仅取消有效时显示「取消」
 */
import { ArrowLeft, X } from 'lucide-react'
import { useState } from 'react'
import { focusQoder } from '../../bridge/client'
import { useAuthorTask } from './AuthorTaskCoordinator'
import { taskStripView } from './taskModel'
import { useFormalProjectShell } from '../projects/FormalProjectShell'

export function TaskStrip() {
  const { task, cancel, navigateToTask } = useAuthorTask()
  const { projects } = useFormalProjectShell()
  const [focusing, setFocusing] = useState(false)

  if (!task || task.status === 'canceled') return null

  const view = taskStripView(task)
  const projectName = task.projectId
    ? (projects.find((p) => p.project_id === task.projectId)?.name ?? null)
    : null

  const goGowrite = async () => {
    setFocusing(true)
    try {
      await focusQoder()
    } catch {
      // 尽力而为：Qoder 未运行时作者自己 Alt+Tab
    } finally {
      setFocusing(false)
    }
  }

  return (
    <div className="task-strip" role="status" aria-label="运行中任务">
      <span className="task-strip-label">
        <strong>{view.label}</strong>
        {projectName ? <em>{projectName}</em> : null}
      </span>
      <span className="task-strip-state">{view.stateText}</span>
      <span className="task-strip-actions">
        {view.primaryAction === 'gowrite' ? (
          <button className="secondary" disabled={focusing} onClick={() => void goGowrite()}>
            {view.primaryLabel}
          </button>
        ) : (
          <button className="secondary" onClick={navigateToTask}>
            <ArrowLeft size={15} />
            {view.primaryLabel}
          </button>
        )}
        {view.canCancel && (
          <button aria-label="取消任务" onClick={() => void cancel()}>
            <X size={15} />
            取消
          </button>
        )}
      </span>
    </div>
  )
}
