import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import {
  clearExecutionAudits,
  getExecutionAudit,
  listExecutionAudits,
  type ExecutionAuditEvent,
  type ExecutionAuditRecord,
  type ExecutionAuditSummary,
} from '../../../bridge/client'
import { auditEventKey } from '../../tasks/taskModel'

const toMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

const operationLabels: Record<string, string> = {
  new_project: '新建作品', story_plan: '大纲与规划', story_write: '正文写作',
  review: '作品检查', material_intake: '素材入库', material_distill: '素材蒸馏',
  source_prepare: '提纯', book_distill: '蒸馏', method_prepare: '方法提纯',
  method_distill: '方法蒸馏', material_scan: '素材扫描',
  material_refresh: '素材刷新',
}

const statusLabels: Record<string, string> = {
  running: '进行中', awaiting_confirmation: '等待确认', completed: '已完成', failed: '失败', canceled: '已取消',
}

const eventKindLabels: Record<string, string> = {
  'operation.started': '操作开始',
  'agent.direct_process_started': 'Agent 进程启动',
  'bridge.waiting': '等待 /gowrite',
  'bridge.response_received': '/gowrite 结果返回',
  'bridge.response_discarded': '过期结果已丢弃',
  'agent.completed': 'Agent 完成',
  'agent.failed': 'Agent 失败',
  'agent.canceled': 'Agent 已取消',
  'skill.started': 'Skill 开始',
  'skill.completed': 'Skill 完成',
  'skill.failed': 'Skill 失败',
  'retrieval.requested': '检索发起',
  'retrieval.package_built': '检索包已生成',
  'retrieval.selected': '检索选中',
  'context.bound': 'Context 绑定',
  'candidate.created': '候选生成',
  'authority.confirmed': '作者确认',
}

const LIVE_STATUSES = new Set(['running', 'awaiting_confirmation'])
const AUTO_REFRESH_INTERVAL_MS = 4000

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return ''
  }
}

function skillRows(events: ExecutionAuditEvent[]) {
  const skills = new Map<string, { started?: number; completed?: number; failed?: number }>()
  for (const event of events) {
    const name = typeof event.details?.skill === 'string' ? event.details.skill : event.component
    if (event.kind === 'skill.started' || event.kind === 'skill.completed' || event.kind === 'skill.failed') {
      const row = skills.get(name) ?? {}
      if (event.kind === 'skill.started') row.started = (row.started ?? 0) + 1
      if (event.kind === 'skill.completed') row.completed = (row.completed ?? 0) + 1
      if (event.kind === 'skill.failed') row.failed = (row.failed ?? 0) + 1
      skills.set(name, row)
    }
  }
  return Array.from(skills.entries()).map(([name, counts]) => ({
    name,
    done: counts.completed ?? 0,
    failed: counts.failed ?? 0,
  }))
}

function retrievalRefs(events: ExecutionAuditEvent[], kind: 'retrieval.package_built' | 'retrieval.selected' | 'context.bound') {
  const refs = new Set<string>()
  for (const event of events) {
    if (event.kind !== kind) continue
    const details = event.details ?? {}
    const list = Array.isArray(details.refs)
      ? (details.refs as unknown[])
      : Array.isArray(details.selection_refs)
        ? (details.selection_refs as unknown[])
        : []
    for (const item of list) {
      if (typeof item === 'string' && item) refs.add(item)
    }
  }
  return Array.from(refs)
}

export function ExecutionAudits() {
  const [records, setRecords] = useState<ExecutionAuditSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [operationFilter, setOperationFilter] = useState('全部')
  const [statusFilter, setStatusFilter] = useState('全部')
  const [openId, setOpenId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ExecutionAuditRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const autoTimerRef = useRef<number | null>(null)

  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const next = await listExecutionAudits({
        limit: 50,
        operation: operationFilter === '全部' ? undefined : operationFilter,
        status: statusFilter === '全部' ? undefined : statusFilter,
      })
      setRecords(next)
      // 明细若正打开：跟随刷新（不自动关闭）
      if (openId) {
        const detailResult = await getExecutionAudit(openId)
        setDetail(detailResult.record)
      }
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [operationFilter, statusFilter, openId])

  useEffect(() => { void reload() }, [reload])

  // 有 running / awaiting_confirmation 记录时适度自动刷新；没有则停止
  useEffect(() => {
    const hasLive = records.some((r) => LIVE_STATUSES.has(r.status ?? ''))
    if (autoTimerRef.current !== null) {
      window.clearTimeout(autoTimerRef.current)
      autoTimerRef.current = null
    }
    if (!hasLive) return
    autoTimerRef.current = window.setTimeout(() => {
      void reload(true)
    }, AUTO_REFRESH_INTERVAL_MS)
    return () => {
      if (autoTimerRef.current !== null) {
        window.clearTimeout(autoTimerRef.current)
        autoTimerRef.current = null
      }
    }
  }, [records, reload])

  const open = useCallback(async (requestId: string) => {
    setOpenId(requestId)
    setDetailLoading(true)
    setDetail(null)
    try {
      const result = await getExecutionAudit(requestId)
      setDetail(result.record)
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const toggleRow = useCallback((requestId: string) => {
    if (openId === requestId) {
      // 真实收起：关闭明细，绝不重新拉取/打开
      setOpenId(null)
      setDetail(null)
      return
    }
    void open(requestId)
  }, [open, openId])

  const clear = useCallback(async () => {
    setClearing(true)
    try {
      const result = await clearExecutionAudits()
      setRecords([])
      setDetail(null)
      setOpenId(null)
      setError(`已清理 ${result.cleared_files} 条记录。`)
    } catch (e) {
      setError(toMessage(e))
    } finally {
      setClearing(false)
    }
  }, [])

  const operations = ['全部', ...Array.from(new Set(records.map((r) => r.operation ?? ''))).filter(Boolean)]
  const statuses = ['全部', ...Array.from(new Set(records.map((r) => r.status ?? ''))).filter(Boolean)]

  return (
    <div className="execution-audits">
      <div className="execution-audits-toolbar">
        <span className="muted-note">本地验证式执行记录（仅机械事件，不含任何提示词或模型输出）。</span>
        <label>
          操作
          <select value={operationFilter} onChange={(e) => setOperationFilter(e.target.value)}>
            {operations.map((op) => <option key={op} value={op}>{operationLabels[op] ?? op}</option>)}
          </select>
        </label>
        <label>
          状态
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            {statuses.map((st) => <option key={st} value={st}>{statusLabels[st] ?? st}</option>)}
          </select>
        </label>
        <button className="secondary" disabled={refreshing || loading} onClick={() => void reload(true)}>
          <RefreshCw /> {refreshing ? '刷新中…' : '刷新记录'}
        </button>
        <button className="secondary" disabled={clearing} onClick={() => void clear()}>
          {clearing ? '清理中…' : '清理记录'}
        </button>
      </div>

      {loading && <p className="muted-note">正在读取执行记录…</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && !error && records.length === 0 && (
        <p className="muted-note">暂无执行记录。运行任一 AI 操作后，这里会显示可验证的执行时间线。</p>
      )}

      {records.length > 0 && (
        <table className="audit-table">
          <thead>
            <tr><th>时间</th><th>操作</th><th>Agent / 模型</th><th>状态</th><th>耗时</th><th /></tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.request_id ?? ''} className={openId === record.request_id ? 'active' : ''}>
                <td>{formatTime(record.started_at)}</td>
                <td>{operationLabels[record.operation ?? ''] ?? record.operation}</td>
                <td>
                  <span className="muted-note">
                    {record.execution_mode === 'interactive_bridge' ? '交互桥' : record.execution_mode === 'direct' ? '直接模式' : record.execution_mode ?? '—'}
                    {record.agent_id ? ` · ${record.agent_id}` : ''}
                    {record.model ? ` · ${record.model}` : ''}
                  </span>
                </td>
                <td><span className={`status-pill ${record.status ?? ''}`}>{statusLabels[record.status ?? ''] ?? record.status}</span></td>
                <td>{record.duration_ms != null ? `${(record.duration_ms / 1000).toFixed(1)}s` : '—'}</td>
                <td>
                  <button onClick={() => toggleRow(record.request_id ?? '')}>
                    {openId === record.request_id ? '收起' : '展开'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openId && (
        <section className="audit-detail">
          <h3>执行时间线</h3>
          {detailLoading && <p className="muted-note">正在读取明细…</p>}
          {detail && (
            <>
              <p className="muted-note">
                {operationLabels[detail.operation ?? ''] ?? detail.operation} · request_id: <code>{detail.request_id}</code>
                {detail.project_id ? ` · 作品: ${detail.project_id}` : ''}
              </p>
              {detail.error && <p className="error-text">错误：{detail.error}</p>}
              {skillRows(detail.events).length > 0 && (
                <p className="muted-note">
                  实际执行的 Skill：
                  {skillRows(detail.events).map((s) => (
                    <span key={s.name} className="soft-tag">
                      {s.name}{s.done > 0 ? ` ✓${s.done}` : ''}{s.failed > 0 ? ` ✗${s.failed}` : ''}
                    </span>
                  ))}
                </p>
              )}
              {(() => {
                const candidates = retrievalRefs(detail.events, 'retrieval.package_built')
                const selected = retrievalRefs(detail.events, 'retrieval.selected')
                const injected = retrievalRefs(detail.events, 'context.bound')
                if (candidates.length === 0 && selected.length === 0 && injected.length === 0) return null
                return (
                  <div className="retrieval-summary">
                    <p className="muted-note">知识检索（KnowledgeRetrieve 实际运行）：</p>
                    <p>候选 {candidates.length > 0 ? candidates.join('、') : '—'}</p>
                    <p>选中 {selected.length > 0 ? selected.join('、') : '—'}</p>
                    <p>注入 Context {injected.length > 0 ? injected.join('、') : '—'}</p>
                  </div>
                )
              })()}
              <ol className="audit-timeline">
                {detail.events.map((event) => (
                  <li key={auditEventKey(event)}>
                    <span className={`event-kind ${event.verified ? 'verified' : ''}`}>
                      {eventKindLabels[event.kind] ?? event.kind}
                    </span>
                    <span className="muted-note">{formatTime(event.at)}</span>
                    {event.verified ? <span className="soft-tag">已验证</span> : null}
                    {event.details && Object.keys(event.details).length > 0 && (
                      <code className="audit-details">{JSON.stringify(event.details)}</code>
                    )}
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>
      )}
    </div>
  )
}
