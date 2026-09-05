import type { MaterialAuthorState, MaterialInboxFile, MaterialItem, MaterialPlanItem } from '../../bridge/client'

export const MATERIAL_TOP_NAVIGATION = ['新增素材', '已提纯素材库', '写作素材库', '素材总览'] as const
export type MaterialTab = typeof MATERIAL_TOP_NAVIGATION[number]

export const MATERIAL_TYPE_FILTERS = ['全部', '原著', '技巧类', '其他'] as const

export const BATCH_TYPE_CHOICES = [
  { value: 'REFERENCE_WORK', label: '原著' },
  { value: 'METHOD_SOURCE', label: '技巧类' },
  { value: 'LOOSE_MATERIAL', label: '其他' },
] as const

export type MaterialWorkflowStage = 'new' | 'purified' | 'writing'

export function authorStateLabel(state: MaterialAuthorState): string {
  return { pending_prepare: '待提纯', pending_distill: '待蒸馏', needs_attention: '需要检查', ready: '可用于写作' }[state]
}

/** 素材工作流阶段以后端投影的 workflow_stage 为准：后端拥有 purification/knowledge/
 * KnowledgeRetrieve 真实事实，能区分 needs_attention 的失败前阶段（提纯失败=new，
 * 蒸馏/验收失败=purified）。仅当旧投影缺失 workflow_stage 时才按 state 兜底。 */
export function deriveWorkflowStage(item: MaterialItem): MaterialWorkflowStage | null {
  if (item.workflow_stage === 'new' || item.workflow_stage === 'purified' || item.workflow_stage === 'writing') {
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

/** 更新入库计划条目（REVIEW → NEW_ASSET 升级；作者手动填写名称和类型后）。 */
export function updatePlanItem(item: MaterialPlanItem, patch: Pick<MaterialPlanItem, 'name' | 'type'>): MaterialPlanItem {
  const updated = { ...item, ...patch }
  if (updated.action === 'REVIEW' && updated.name?.trim() && updated.type) {
    return { ...updated, action: 'NEW_ASSET', reason: undefined }
  }
  return updated
}
