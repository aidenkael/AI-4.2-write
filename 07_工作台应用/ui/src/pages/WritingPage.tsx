import { Bot, Check, CircleCheck, FolderOpen, PenLine, Plus, RefreshCw, Save, Sparkles, X } from 'lucide-react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useWritingController } from '../features/writing/useWritingController'
import { StatusBadge } from '../components/StatusBadge'

/**
 * 正在写：三区工作台（左章节导航 / 中正式已采用正文 / 右唯一 AI 协作区）。
 *
 * - 右侧只有一个协作面板：动作前保持安静，候选只在实际生成后出现；
 *   不再同时存在常驻的“AI 助手”与“AI 候选稿”两个重复面板；
 * - 保留 StoryWrite 两阶段执行与候选接受流程；正式正文使用显式保存；
 * - 新章节、stale guard、修订索引与语义同步都走真实后端合同，无假 autosave。
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
            <h2>正在写</h2>
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
        {state.writingSurface?.chapters.map((ch) => (
          <button
            key={ch.chapter_number}
            className={selectedChapter?.chapter_number === ch.chapter_number ? 'active' : ''}
            onClick={() => c.selectChapter(ch.chapter_number)}
          >
            {ch.scene_count > 0 && <CircleCheck />}
            <span>
              <span>{ch.title}</span>
              <small>
                {ch.words ? `${ch.words.toLocaleString()} 字` : '未开始'}
                {ch.scene_count > 0 ? ` · ${ch.scene_count} 段` : ''}
              </small>
            </span>
          </button>
        ))}
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
        <textarea
          aria-label="正式正文编辑器"
          value={state.editorContent}
          onChange={(event) => c.setEditorContent(event.target.value)}
          disabled={!selectedChapter?.content_sha256}
          placeholder={selectedChapter?.content_sha256 ? '开始写这一章…' : '这是尚未创建的章节位置。点击左侧“+”新建正式章节后即可编辑。'}
        />
        <footer>
          <span>
            {selectedChapter ? `${state.editorContent.length.toLocaleString()} 字` : ''}
            {selectedChapter && selectedChapter.scene_count > 0
              ? `　已收录 ${selectedChapter.scene_count} 段`
              : ''}
          </span>
          <div className="editor-save-actions">
            {state.editorDirty && <span className="unsaved-note">有未保存修改</span>}
            <button disabled={!state.editorDirty || state.saving} onClick={() => void c.save(false)}><Save /> 仅保存</button>
            <button className="primary" disabled={!state.editorDirty || state.saving} onClick={() => void c.save(true)}><Save /> 保存并同步</button>
          </div>
        </footer>

        {state.settlementStatus === 'syncing' && <div className="sync-warning">正文已保存，正在增量同步人物、关系、事件、时间与伏笔状态…</div>}
        {state.pendingChanges.map((change) => {
          const consequences = change.semantic?.consequences ?? []
          const undecidedIndexes = consequences
            .map((item, index) => item.classification !== 'mechanically_certain' ? index : -1)
            .filter((index) => index >= 0)
          return (
            <section className="settlement-card" key={change.change_id}>
              <strong>{change.status === 'awaiting_author' ? '有语义后果需要你决定' : change.status === 'failed' ? '作品状态同步失败' : '作品状态等待同步'}</strong>
              {change.semantic?.summary && <p>{change.semantic.summary}</p>}
              {change.error && <p className="error-text">{change.error}</p>}
              {change.status === 'awaiting_author' && (
                <ul>{undecidedIndexes.map((index) => <li key={index}>{String(consequences[index].title ?? '未命名后果')} · {String(consequences[index].reason ?? '')}</li>)}</ul>
              )}
              <div className="candidate-actions">
                {(change.status === 'failed' || change.status === 'pending') && <button onClick={() => void c.retrySettlement(change.change_id)}><RefreshCw /> 重试同步</button>}
                {change.status === 'awaiting_author' && <><button className="primary" onClick={() => void c.confirmConsequences(change.change_id, undecidedIndexes)}>采用这些后果</button><button onClick={() => void c.confirmConsequences(change.change_id, [])}>只保留正文</button></>}
              </div>
            </section>
          )
        })}
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
                <>{state.execution?.execution_mode === 'direct' ? '后台 AI 正在执行（直接模式）…' : '正在准备执行…'}</>
              )}
            </div>
            {state.execution?.execution_mode === 'interactive_bridge' && (
              <p className="muted-note execution-summary">
                交互桥已就绪：任务已交给 Qoder，请在 Qoder 会话中执行 /gowrite。
              </p>
            )}
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
            <ExecutionSummary execution={state.execution} />
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
          <button onClick={() => c.setAuthorInput('顺着上一段继续写下去')}>
            <PenLine />
            接下来怎么写
          </button>
          <button
            onClick={() => {
              // 方案讨论属于规划，不属于正文写作：交给故事规划（StoryPlan）
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
