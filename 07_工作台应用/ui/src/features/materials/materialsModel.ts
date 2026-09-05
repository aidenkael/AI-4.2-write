import type { MaterialAuthorState, MaterialInboxFile, MaterialItem } from '../../bridge/client'

export const MATERIAL_TOP_NAVIGATION = ['新增素材', '已提纯素材库', '写作素材库', '素材总览'] as const
export type MaterialTab = typeof MATERIAL_TOP_NAVIGATION[number]

export const MATERIAL_TYPE_FILTERS = ['全部', '原著', '技巧类', '其他'] as const

export const BATCH_TYPE_CHOICES = [
  { value: 'REFERENCE_WORK', label: '原著' },
  { value: 'METHOD_SOURCE', label: '技巧类' },
  { value: 'LOOSE_MATERIAL', label: '其他' },
] as const

/** 作者未选批次类型时的默认值：必须为空（未选时主按钮 disabled，不猜默认类型）。 */
export const DEFAULT_BATCH_TYPE = ''

export type MaterialWorkflowStage = 'new' | 'purified' | 'writing' | 'other'

/** 新增素材区唯一主按钮：未选类型 disabled；原著/技巧类=提纯；其他=保存素材。
 *  running 时显示进行中文案并 disabled（防重复点击）。纯函数，供机械测试。 */
export function inboxPrimaryAction(batchType: string, processing: boolean): { label: string; disabled: boolean } {
  const isOther = batchType === 'LOOSE_MATERIAL'
  if (!batchType) return { label: '提纯', disabled: true }
  if (processing) return { label: isOther ? '正在保存…' : '正在提纯…', disabled: true }
  return { label: isOther ? '保存素材' : '提纯', disabled: false }
}

export function authorStateLabel(state: MaterialAuthorState): string {
  return { pending_prepare: '待提纯', pending_distill: '待蒸馏', needs_attention: '需要检查', ready: '可用于写作' }[state]
}

/** 素材工作流阶段以后端投影的 workflow_stage 为准：后端拥有 purification/knowledge/
 * KnowledgeRetrieve 真实事实，能区分 needs_attention 的失败前阶段（提纯失败=new，
 * 蒸馏/验收失败=purified）以及其他/研究资料（other）。直接信任后端四种值；
 * 仅当旧投影缺失 workflow_stage 时才按 state 兜底。 */
export function deriveWorkflowStage(item: MaterialItem): MaterialWorkflowStage | null {
  if (item.workflow_stage === 'new' || item.workflow_stage === 'purified'
    || item.workflow_stage === 'writing' || item.workflow_stage === 'other') {
    return item.workflow_stage
  }
  if (item.state === 'ready') return 'writing'
  if (item.state === 'pending_distill') return 'purified'
  if (item.state === 'pending_prepare' || item.state === 'needs_attention') return 'new'
  return null
}

export function materialsForStage(items: MaterialItem[], stage: MaterialWorkflowStage): MaterialItem[] {
  return items.filter((item) => deriveWorkflowStage(item) === stage)
}

/** 书籍卡紧凑信息行：类型 · 真实格式 · 作者（例：原著 · EPUB · 马伯庸）。
 *  格式只来自 source_formats（asset.files 后缀派生）；缺项自动省略，绝不堆状态解释。 */
export function materialCardMeta(item: { type_label: string; source_formats: string[]; author: string }): string {
  const parts: string[] = []
  if (item.type_label) parts.push(item.type_label)
  if (item.source_formats?.length) parts.push(item.source_formats.join(' / '))
  if (item.author) parts.push(item.author)
  return parts.join(' · ')
}

/** needs_attention 的重试动作标签：由失败前阶段决定重试类型（CP3.5）。
 *  new → 重新提纯；purified → 重新蒸馏；writing 不应处于 needs_attention。 */
export function attentionRetryLabel(stage: MaterialWorkflowStage | null | undefined): string | null {
  if (stage === 'new') return '重新提纯'
  if (stage === 'purified') return '重新蒸馏'
  return null
}

/** 工作流阶段 → 作者可读区域名（素材总览“需要重新处理”标注所属阶段用）。 */
export function workflowStageLabel(stage: MaterialWorkflowStage | null): string {
  if (stage === 'new') return '新增素材'
  if (stage === 'purified') return '已提纯素材库'
  if (stage === 'writing') return '写作素材库'
  return ''
}

/** 素材总览的类型分布（原著 / 技巧类 / 其他）；其他含 LOOSE_MATERIAL 与 RESEARCH。 */
export function countMaterialsByType(items: MaterialItem[]): { reference: number; method: number; other: number } {
  let reference = 0
  let method = 0
  let other = 0
  for (const item of items) {
    if (item.type === 'REFERENCE_WORK') reference += 1
    else if (item.type === 'METHOD_SOURCE') method += 1
    else other += 1
  }
  return { reference, method, other }
}

export function matchesMaterialFilter(item: MaterialItem, filter: string): boolean {
  if (filter === '全部') return true
  if (filter === '原著') return item.type === 'REFERENCE_WORK'
  if (filter === '技巧类') return item.type === 'METHOD_SOURCE'
  if (filter === '其他') return item.type === 'LOOSE_MATERIAL' || item.type === 'RESEARCH'
  return true
}

export function needsAttentionMaterials(items: MaterialItem[]): MaterialItem[] {
  return items.filter((item) => item.author_group === 'needs_attention')
}

export function pendingInboxBadgeCount(inbox: MaterialInboxFile[], items: MaterialItem[]): number {
  return inbox.filter((file) => !file.unsupported).length + needsAttentionMaterials(items).length
}

export function attachedMaterialName(assetId: string | undefined, items: MaterialItem[]): string {
  return items.find((item) => item.id === assetId)?.name || assetId || ''
}
