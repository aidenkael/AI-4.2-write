/**
 * 灵感箱真实本地收件箱消费者控制器。
 *
 * 约束：灵感是非权威本地笔记；list/create/delete/markUsed 均为真实后端
 * （ideas.json 原子存储），绝不调用模型、绝不进入 Story State。
 */
import { useCallback, useEffect, useState } from 'react'
import {
  createIdea,
  deleteIdea,
  listIdeas,
  markIdeaUsed,
  type IdeaItem,
  type IdeaKind,
} from '../../bridge/client'

export interface IdeasController {
  ideas: IdeaItem[]
  loading: boolean
  error: string | null
  reload(): Promise<void>
  add(content: string, kind: IdeaKind): Promise<IdeaItem | null>
  remove(ideaId: string): Promise<void>
  markUsed(ideaId: string, projectId: string): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useIdeasController(options?: { notify?: (message: string) => void }): IdeasController {
  const notify = options?.notify
  const [ideas, setIdeas] = useState<IdeaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setIdeas(await listIdeas())
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const add = useCallback(async (content: string, kind: IdeaKind) => {
    const trimmed = content.trim()
    if (!trimmed) return null
    try {
      const idea = await createIdea({ content: trimmed, kind })
      setIdeas((current) => [idea, ...current])
      return idea
    } catch (e) {
      setError(toMessage(e))
      return null
    }
  }, [])

  const remove = useCallback(async (ideaId: string) => {
    try {
      await deleteIdea(ideaId)
      setIdeas((current) => current.filter((i) => i.id !== ideaId))
    } catch (e) {
      setError(toMessage(e))
    }
  }, [])

  const markUsed = useCallback(async (ideaId: string, projectId: string) => {
    try {
      const updated = await markIdeaUsed({ idea_id: ideaId, project_id: projectId })
      setIdeas((current) => current.map((i) => (i.id === ideaId ? updated : i)))
      notify?.('已把这条灵感标记为已用于该作品。')
    } catch (e) {
      setError(toMessage(e))
    }
  }, [notify])

  return { ideas, loading, error, reload, add, remove, markUsed }
}
