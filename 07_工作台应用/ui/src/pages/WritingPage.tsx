import { Bot, Check, CircleCheck, FolderOpen, PenLine, RefreshCw, Sparkles, X } from 'lucide-react'
import { ExecutionSummary } from '../components/ExecutionSummary'
import { useApp } from '../features/app/AppStore'
import { useFormalProjectShell } from '../features/projects/FormalProjectShell'
import { useWritingController } from '../features/writing/useWritingController'
import { StatusBadge } from '../components/StatusBadge'

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

  // 未选择正式作品：安全空态 + 返回作品列表；绝不在这里自动挑选项目
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
            <p>请先在「我的作品」中选择一部正式作品。</p>
            <button className="primary" onClick={() => actions.navigate('projects')}>
              <FolderOpen />
              返回作品列表
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
            <span className="readonly-label">
              <CircleCheck size={15} />
              已采用正文（只读）
            </span>
            {state.writingSurface ? `${state.writingSurface.total_words.toLocaleString()} 字` : ''}
          </span>
        </header>
        <textarea
          aria-label="已采用正文（只读）"
          value={selectedChapter?.content ?? ''}
          readOnly
          placeholder="还没有已采用的正文。在右侧写下这一段想写什么，生成候选并确认后，正文会出现在这里。"
        />
        <footer>
          <span>
            {selectedChapter ? `${selectedChapter.words.toLocaleString()} 字` : ''}
            {selectedChapter && selectedChapter.scene_count > 0
              ? `　已收录 ${selectedChapter.scene_count} 段`
              : ''}
          </span>
          <span>
            <CircleCheck size={15} />
            正式正文，来自作品工程
          </span>
        </footer>
      </section>

      <aside className="writing-side">
        <section className="panel assistant">
          <header>
            <h2>
              <Sparkles />
              AI 助手
            </h2>
          </header>
          <h3>现在建议</h3>
          <div className="suggestion">
            写下这一段想写什么。AI 会先挑选相关上下文、再生成候选正文；候选未经你确认不会写入正式作品。
          </div>
          <button onClick={() => c.setAuthorInput('顺着上一段继续写下去')}>
            <PenLine />
            接下来怎么写
          </button>
          <button
            onClick={() => {
              // 方案讨论属于规划，不属于正文写作：交给 Development/StoryPlan
              // 一次性预填（项目绑定、session-only），绝不自动提交，绝不生成正文。
              if (selected) {
                actions.setDevelopmentPrefill({
                  project_id: selected.project_id,
                  text: '给我几个接下来可以发展的情节方向',
                })
                actions.setProjectSection('development')
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
            ▣ 检查这段
          </button>
        </section>

        <section className="panel prose-candidate">
          <header>
            <h2>
              <Sparkles />
              AI 候选稿
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
        </section>
      </aside>
    </div>
  )
}
