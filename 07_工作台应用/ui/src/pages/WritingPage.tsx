import { Bot, Check, CircleCheck, FolderOpen, Plus, RefreshCw, Save, Sparkles, X } from 'lucide-react'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useWritingController } from '../features/writing/useWritingController'
import { StatusBadge } from '../components/StatusBadge'
import type { StoryWriteChapter } from '../bridge/client'

/**
 * 正文管理：三区工作台（左章节导航 / 中正式已采用正文 / 右唯一 AI 协作区）。
 *
 * - 右侧只有一个协作面板：动作前保持安静，候选只在实际生成后出现；
 *   不再同时存在常驻的“AI 助手”与“AI 候选稿”两个重复面板；
 * - 保留 StoryWrite 两阶段执行与候选接受流程；正式正文使用显式保存；
 * - 新章节、stale guard、修订索引与作者触发的作品状态整理都走真实后端合同。
 */

export function WritingPage() {
  const { actions } = useApp()
  const { selected } = useFormalProjectShell()
  const c = useWritingController({ projectId: selected?.project_id ?? null, notify: actions.notify })
  const { state } = c
  const selectedChapter =
    state.writingSurface?.chapters.find((ch) => ch.chapter_number === state.selectedChapterNumber) ??
    state.writingSurface?.chapters[0] ??
    null
  const canGenerate = !!selected && state.authorInput.trim().length > 0 && !state.requestId
  const fineOutline = selectedChapter?.fine_outline ?? {}
  const outlineText = (key: string) => typeof fineOutline[key] === 'string' ? String(fineOutline[key]) : ''
  const chapterGroups = (state.writingSurface?.chapters ?? []).reduce<Array<{ key: string; title: string; chapters: StoryWriteChapter[] }>>((groups, chapter) => {
    const key = chapter.stage_ref || 'unassigned'
    const title = chapter.stage_title || '未分卷'
    const group = groups.find((item) => item.key === key)
    if (group) group.chapters.push(chapter)
    else groups.push({ key, title, chapters: [chapter] })
    return groups
  }, [])
  const previousActual = selectedChapter?.previous_actual_result
  const previousSummary = previousActual && typeof previousActual.summary === 'string'
    ? previousActual.summary
    : ''

  // 未选择正式作品：安全空态 + 返回作品页；绝不在这里自动挑选项目
  if (!selected) {
    return (
      <div className="writing-layout">
        <aside className="panel chapters">
          <header>
            <h2>章节目录</h2>
          </header>
          <div className="empty-state">请先选择正式作品。</div>
        </aside>
        <section className="panel editor">
          <header>
            <h2>正文管理</h2>
          </header>
          <div className="empty-state">
            <p>请先在「作品」中选择一部正式作品。</p>
            <button className="primary" onClick={() => actions.navigate('works')}>
              <FolderOpen />
              返回作品
            </button>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="writing-layout">
      <aside className="panel chapters">
        <header>
          <h2>章节目录</h2>
          <button aria-label="新建章节" disabled={state.saving || state.editorDirty} onClick={() => void c.createChapter()}><Plus /></button>
        </header>
        <div className="chapter-group-list">
          {chapterGroups.map((group) => (
            <section className="chapter-group" key={group.key}>
              <div className="chapter-group-title">{group.title}</div>
              {group.chapters.map((ch) => (
                <button
                  key={ch.chapter_number}
                  className={selectedChapter?.chapter_number === ch.chapter_number ? 'active' : ''}
                  onClick={() => c.selectChapter(ch.chapter_number)}
                >
                  {ch.scene_count > 0 && <CircleCheck />}
                  <span>
                    <span>{ch.title}</span>
                    <small>
                      {ch.formal_prose_exists ? `${ch.words.toLocaleString()} 字` : '计划中'}
                      {ch.scene_count > 0 ? ` · ${ch.scene_count} 段` : ''}
                    </small>
                  </span>
                </button>
              ))}
            </section>
          ))}
        </div>
      </aside>

      <section className="panel editor">
        <header>
          <h2>{selectedChapter ? selectedChapter.title : '已采用正文'}</h2>
          <span>
            <span className="readonly-label editable-label">
              <CircleCheck size={15} />
              正式正文 · 显式保存
            </span>
            {state.writingSurface ? `${state.writingSurface.total_words.toLocaleString()} 字` : ''}
          </span>
        </header>
        {selectedChapter && (
          <section className="writing-context-strip">
            <p><b>本章目的：</b>{outlineText('task') || '尚未填写'}</p>
            <p><b>目标字数：</b>{
              typeof fineOutline.min_words === 'number' && typeof fineOutline.max_words === 'number'
                ? `${fineOutline.min_words}–${fineOutline.max_words} 字`
                : '尚未设置'
            }</p>
            {previousSummary && <p><b>上一章实际回顾：</b>{previousSummary}</p>}
            {(state.writingSurface?.open_threads?.length ?? 0) > 0 && (
              <p><b>当前线索：</b>{state.writingSurface?.open_threads?.map((item) => item.title).join('、')}</p>
            )}
          </section>
        )}
        <textarea
          aria-label="正式正文编辑器"
          value={state.editorContent}
          onChange={(event) => c.setEditorContent(event.target.value)}
          disabled={!selectedChapter?.formal_prose_exists}
          placeholder={selectedChapter?.formal_prose_exists ? '开始写这一章…' : '这是已规划但尚未创建正文的章节。点击“开始本章”后即可编辑。'}
        />
        <footer>
          <span>
            {selectedChapter ? `${state.editorContent.length.toLocaleString()} 字` : ''}
            {selectedChapter && selectedChapter.scene_count > 0
              ? `　已收录 ${selectedChapter.scene_count} 段`
              : ''}
          </span>
          <div className="editor-save-actions">
            {state.editorDirty ? <span className="unsaved-note">未保存</span> : selectedChapter?.formal_prose_exists ? <span className="muted-note">已保存</span> : null}
            {selectedChapter && !selectedChapter.formal_prose_exists && (
              <button className="primary" disabled={state.saving} onClick={() => void c.createChapter(selectedChapter.chapter_number)}>
                <Plus />
                开始本章
              </button>
            )}
            <button className="primary" disabled={!state.editorDirty || state.saving} onClick={() => void c.save()}><Save /> 保存</button>
          </div>
        </footer>

      </section>

      <aside className="panel ai-collab">
        <header>
          <h2>
            <Sparkles />
            AI 协作
          </h2>
          {(state.status === 'running' ||
            state.status === 'waiting_confirmation' ||
            state.status === 'accepted' ||
            state.status === 'failed') && <StatusBadge status={state.status} />}
        </header>

        {state.status === 'loading' && (
          <div className="running">
            <span />
            正在加载正式写作数据…
          </div>
        )}

        {(state.status === 'running' ||
          state.status === 'waiting_gowrite' ||
          state.status === 'waiting_prose_gowrite') && (
          <>
            <div className="running">
              <span />
              {state.status === 'waiting_gowrite' && (
                <>{state.phaseMessage ?? '等待 Qoder /gowrite：正在选择本次写作上下文'}</>
              )}
              {state.status === 'waiting_prose_gowrite' && (
                <>{state.phaseMessage ?? '上下文已准备好，请再次执行 /gowrite 生成正文'}</>
              )}
              {state.status === 'running' && (
                <>{state.execution?.execution_mode === 'interactive_bridge' ? '请到 Qoder 执行 /gowrite' : 'AI 正在写作'}</>
              )}
            </div>
            <div className="candidate-actions">
              <button onClick={() => void c.cancel()}>
                <X />
                取消
              </button>
            </div>
          </>
        )}

        {state.status === 'confirming' && (
          <>
            <textarea
              aria-label="候选正文（只读）"
              className="candidate-view"
              value={state.candidate?.draft_text ?? ''}
              readOnly
            />
            <div className="confirming-note">正在采用…</div>
          </>
        )}

        {state.status === 'waiting_confirmation' && state.candidate && (
          <>
            <textarea
              aria-label="候选正文（只读）"
              className="candidate-view"
              value={state.candidate.draft_text}
              readOnly
            />
            <div className="candidate-actions">
              <button className="primary" onClick={() => void c.confirm()}>
                <Check />
                采用
              </button>
              <button onClick={() => void c.regenerate()}>
                <RefreshCw />
                换一种
              </button>
              <button onClick={() => void c.discard()}>不用了</button>
            </div>
          </>
        )}

        {state.status === 'accepted' && (
          <span className="accepted-note">
            <Check />
            已采用，正文已从正式作品刷新。
          </span>
        )}

        {(state.status === 'idle' || state.status === 'failed' || state.status === 'accepted') && (
          <>
            <input
              value={state.authorInput}
              onChange={(e) => c.setAuthorInput(e.target.value)}
              placeholder="这一段想写什么？"
            />
            <button className="primary wide" disabled={!canGenerate} onClick={() => void c.generate()}>
              <Sparkles />
              生成候选正文
            </button>
          </>
        )}

        {state.error && <p className="error-text">{state.error}</p>}

        <footer className="ai-collab-shortcuts">
          <button
            onClick={() => {
              // 方案讨论属于规划，不属于正文写作：交给大纲与规划（StoryPlan）
              // 一次性预填（项目绑定、session-only），绝不自动提交，绝不生成正文。
              if (selected) {
                actions.setPlanningPrefill({
                  project_id: selected.project_id,
                  text: '给我几个接下来可以发展的情节方向',
                })
                actions.setProjectSection('planning')
              }
            }}
          >
            <Bot />
            给我几个方案
          </button>
          <button
            onClick={() => {
              // 章节交接：session-only，Review 消费一次并选中该章节，绝不自动运行
              if (selected && state.selectedChapterNumber != null) {
                actions.setReviewChapterHandoff({
                  project_id: selected.project_id,
                  chapter_number: state.selectedChapterNumber,
                })
              }
              actions.setProjectSection('review')
            }}
          >
            ▣ 检查这章
          </button>
        </footer>
      </aside>
    </div>
  )
}
