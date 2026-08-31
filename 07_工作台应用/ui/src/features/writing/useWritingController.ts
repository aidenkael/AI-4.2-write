/**
 * WritingPage 真实 StoryWrite 消费者控制器（App 级协调器消费者）。
 *
 * 根不变量：AI 任务属于 Go Write（AuthorTaskCoordinator），不属于页面。
 * 本控制器只保留页面本地输入/展示状态（写作面、选中章节、作者输入、
 * 瞬时"已采用"提示），一切任务状态（request_id / 阶段 / 候选 / 错误）都
 * 来自协调器；卸载/导航绝不影响任务推进与候选保留。
 *
 * 约束：
 * - 候选是后端持有（只读），confirm 只回传 { project_id, writing_token }；
 * - 项目切换绝不把另一项目的任务/候选带到本页（按 projectId 过滤展示）；
 * - 跨项目 token 校验由后端强制。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createChapter as createFormalChapter,
  getStoryWriteSurface,
  saveFormalProse,
  type ProposeStoryWriteResult,
  type StoryWriteSurface,
} from '../../bridge/client'
import { useAuthorTask } from '../tasks/AuthorTaskCoordinator'

export type WritingStatus =
  | 'loading'
  | 'idle'
  | 'running'
  | 'waiting_gowrite'
  | 'waiting_prose_gowrite'
  | 'waiting_confirmation'
  | 'confirming'
  | 'accepted'
  | 'failed'

export type WritingPhase = 'pending_selection' | 'pending_prose' | null

export interface WritingControllerState {
  writingSurface: StoryWriteSurface | null
  selectedChapterNumber: number | null
  authorInput: string
  requestId: string | null
  writingToken: string | null
  candidate: ProposeStoryWriteResult | null
  status: WritingStatus
  /** 交互桥阶段（pending_selection / pending_prose；Direct 为 null）。 */
  phase: WritingPhase
  /** 后端返回的作者可读阶段提示。 */
  phaseMessage: string | null
  error: string | null
  /** 后端返回的非机密执行元数据（execution_mode / agent_id / model）。 */
  execution: { execution_mode?: string; agent_id?: string | null; model?: string | null } | null
  editorContent: string
  editorDirty: boolean
  saving: boolean
}

export interface WritingController {
  state: WritingControllerState
  selectChapter(chapterNumber: number): void
  setAuthorInput(input: string): void
  setEditorContent(input: string): void
  createChapter(): Promise<void>
  save(): Promise<void>
  generate(): Promise<void>
  cancel(): Promise<void>
  discard(): Promise<void>
  regenerate(): Promise<void>
  confirm(): Promise<void>
}

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** 协调器任务 → 本页可见状态（仅匹配本项目；另一项目的任务不影响本页）。 */
function taskViewForProject(
  task: ReturnType<typeof useAuthorTask>['task'],
  projectId: string | null,
): Pick<WritingControllerState, 'requestId' | 'writingToken' | 'candidate' | 'status' | 'phase' | 'phaseMessage' | 'error' | 'execution'> | null {
  if (!task || task.kind !== 'story_write') return null
  if (projectId && task.projectId && task.projectId !== projectId) return null
  const base = {
    requestId: task.requestId || null,
    writingToken: null as string | null,
    candidate: null as ProposeStoryWriteResult | null,
    phase: null as WritingPhase,
    phaseMessage: task.message,
    error: task.error,
    execution: task.execution
      ? {
          execution_mode: task.execution.execution_mode ?? undefined,
          agent_id: task.execution.agent_id ?? null,
          model: task.execution.model ?? null,
        }
      : null,
  }
  switch (task.status) {
    case 'running':
      return { ...base, status: 'running' }
    case 'waiting_author':
      if (task.phase === 'pending_prose') {
        return { ...base, status: 'waiting_prose_gowrite', phase: 'pending_prose' }
      }
      return { ...base, status: 'waiting_gowrite', phase: 'pending_selection' }
    case 'candidate': {
      const result = task.result as ProposeStoryWriteResult | null
      return { ...base, status: 'waiting_confirmation', writingToken: result?.writing_token ?? null, candidate: result }
    }
    case 'confirming':
      return { ...base, status: 'confirming' }
    case 'failed':
      return { ...base, status: 'failed' }
    default:
      return null
  }
}

export function useWritingController(options: {
  projectId: string | null
  notify?: (message: string) => void
}): WritingController {
  const { projectId, notify } = options
  const { task, start, cancel: cancelTask, confirm: confirmTask } = useAuthorTask()
  const [writingSurface, setWritingSurface] = useState<StoryWriteSurface | null>(null)
  const [selectedChapterNumber, setSelectedChapterNumber] = useState<number | null>(null)
  const [authorInput, setAuthorInputState] = useState('')
  const [acceptedNote, setAcceptedNote] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [surfaceLoading, setSurfaceLoading] = useState(true)
  const [surfaceError, setSurfaceError] = useState<string | null>(null)
  const [editorContent, setEditorContentState] = useState('')
  const [editorDirty, setEditorDirty] = useState(false)
  const [saving, setSaving] = useState(false)

  const projectRef = useRef<string | null>(projectId)
  projectRef.current = projectId

  const loadSurface = useCallback(async (pid: string) => {
    setSurfaceLoading(true)
    setSurfaceError(null)
    try {
      const surface = await getStoryWriteSurface(pid)
      if (projectRef.current !== pid) return // 加载期间已切换项目 → 丢弃过期结果
      if (surface.project_id !== pid) throw new Error('返回的写作数据与当前作品不一致，已拒绝。')
      setWritingSurface(surface)
      setSelectedChapterNumber((current) => {
        const next = current != null && surface.chapters.some((chapter) => chapter.chapter_number === current)
          ? current
          : surface.active_chapter_number
        const chapter = surface.chapters.find((item) => item.chapter_number === next)
        setEditorContentState(chapter?.content ?? '')
        setEditorDirty(false)
        return next
      })
    } catch (e) {
      if (projectRef.current !== pid) return
      setSurfaceError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setSurfaceLoading(false)
    }
  }, [])

  // 项目切换/挂载：重新加载正式写作面（只读数据，与任务生命周期无关）
  useEffect(() => {
    setAcceptedNote(false)
    setLocalError(null)
    setWritingSurface(null)
    setSelectedChapterNumber(null)
    if (!projectId) {
      setSurfaceLoading(false)
      return
    }
    void loadSurface(projectId)
  }, [projectId, loadSurface])

  const view = taskViewForProject(task, projectId)
  const candidate = view?.candidate ?? null

  const state: WritingControllerState = {
    writingSurface,
    selectedChapterNumber,
    authorInput,
    requestId: view?.requestId ?? null,
    writingToken: view?.writingToken ?? null,
    candidate,
    status: surfaceLoading
      ? 'loading'
      : view?.status ?? (acceptedNote ? 'accepted' : 'idle'),
    phase: view?.phase ?? null,
    phaseMessage: view?.phaseMessage ?? null,
    error: view?.error ?? surfaceError ?? localError,
    execution: view?.execution ?? null,
    editorContent,
    editorDirty,
    saving,
  }

  const setAuthorInput = useCallback((input: string) => {
    setAuthorInputState(input)
    setLocalError(null)
  }, [])

  const selectChapter = useCallback((chapterNumber: number) => {
    if (editorDirty && chapterNumber !== selectedChapterNumber) {
      setLocalError('当前正文有未保存修改，请先保存后再切换章节。')
      return
    }
    setSelectedChapterNumber(chapterNumber)
    const chapter = writingSurface?.chapters.find((item) => item.chapter_number === chapterNumber)
    setEditorContentState(chapter?.content ?? '')
    setEditorDirty(false)
    setLocalError(null)
  }, [editorDirty, selectedChapterNumber, writingSurface?.chapters])

  const setEditorContent = useCallback((input: string) => {
    setEditorContentState(input)
    setEditorDirty(true)
    setLocalError(null)
  }, [])


  const createChapter = useCallback(async () => {
    const pid = projectRef.current
    if (!pid || !writingSurface || writingSurface.project_id !== pid) return
    const onlyVirtualFirst = writingSurface.chapters.length === 1
      && writingSurface.chapters[0].chapter_number === 1
      && !writingSurface.chapters[0].content_sha256
    const next = onlyVirtualFirst
      ? 1
      : Math.max(0, ...writingSurface.chapters.map((chapter) => chapter.chapter_number)) + 1
    setSaving(true)
    setLocalError(null)
    try {
      await createFormalChapter({ project_id: pid, chapter_number: next })
      await loadSurface(pid)
      setSelectedChapterNumber(next)
      setEditorContentState('')
      setEditorDirty(false)
    } catch (e) {
      setLocalError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setSaving(false)
    }
  }, [loadSurface, writingSurface])

  const save = useCallback(async () => {
    const pid = projectRef.current
    const chapter = writingSurface?.project_id === pid
      ? writingSurface.chapters.find((item) => item.chapter_number === selectedChapterNumber)
      : undefined
    if (!pid || !chapter) return
    if (!chapter.content_sha256) {
      setLocalError('请先新建正式章节，再保存正文。')
      return
    }
    if (!editorDirty) return
    setSaving(true)
    setLocalError(null)
    try {
      const result = await saveFormalProse({
        project_id: pid, chapter_number: chapter.chapter_number,
        base_content_sha256: chapter.content_sha256, content: editorContent,
      })
      await loadSurface(pid)
      setSelectedChapterNumber(chapter.chapter_number)
      setEditorContentState(editorContent)
      setEditorDirty(false)
      notify?.(result.message)
    } catch (e) {
      setLocalError(toMessage(e))
    } finally {
      if (projectRef.current === pid) setSaving(false)
    }
  }, [editorContent, editorDirty, loadSurface, notify, selectedChapterNumber, writingSurface?.chapters])

  const generate = useCallback(async () => {
    const pid = projectRef.current
    const input = authorInput.trim()
    if (!pid) {
      setLocalError('请先选择正式作品。')
      return
    }
    if (!input) {
      setLocalError('请先写下这一段想写什么。')
      return
    }
    setAcceptedNote(false)
    const busy = await start({
      kind: 'story_write', project_id: pid, author_input: input,
      chapter_number: selectedChapterNumber ?? undefined,
    })
    if (busy) setLocalError(busy)
  }, [authorInput, selectedChapterNumber, start])

  const cancel = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const discard = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
  }, [cancelTask])

  const regenerate = useCallback(async () => {
    setAcceptedNote(false)
    setLocalError(null)
    await cancelTask()
    await generate()
  }, [cancelTask, generate])

  const confirm = useCallback(async () => {
    const pid = projectRef.current
    if (!pid || !candidate) {
      setLocalError('缺少确认信息，请重新生成。')
      return
    }
    try {
      const confirmed = await confirmTask('story_write')
      if (!confirmed) {
        setLocalError(task?.error ?? '确认失败，请重试。')
        return
      }
      // 以正式项目为真相：确认后重新加载写作面
      await loadSurface(pid)
      setAcceptedNote(true)
      const result = confirmed as { chapter_number?: number }
      if (result.chapter_number != null) setSelectedChapterNumber(result.chapter_number)
      notify?.('这段已经保留下来了。')
    } catch (e) {
      setLocalError(toMessage(e))
    }
  }, [candidate, confirmTask, loadSurface, notify, task?.error])

  return {
    state,
    selectChapter,
    setAuthorInput,
    setEditorContent,
    createChapter,
    save,
    generate,
    cancel,
    discard,
    regenerate,
    confirm,
  }
}
