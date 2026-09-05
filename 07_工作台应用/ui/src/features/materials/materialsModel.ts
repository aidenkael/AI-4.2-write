import type { MaterialAuthorState, MaterialInboxFile, MaterialItem, MaterialPlanItem } from '../../bridge/client'

export const MATERIAL_TOP_NAVIGATION = ['待处理', '素材库', '可用于写作'] as const
export const MATERIAL_TYPE_FILTERS = ['全部', '原著', '技巧书', '其他'] as const

export function authorStateLabel(state: MaterialAuthorState): string {
  return { pending_prepare: '待提纯', pending_distill: '待蒸馏', needs_attention: '需要检查', ready: '可用于写作' }[state]
}

export function matchesMaterialFilter(item: MaterialItem, filter: string): boolean {
  if (filter === '全部') return true
  if (filter === '其他') return ['研究资料', '零散素材', '待确认'].includes(item.type_label)
  return item.type_label === filter
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

export function updateClassifyPlanItem(item: MaterialPlanItem, patch: Pick<MaterialPlanItem, 'name' | 'type'>): MaterialPlanItem {
  const updated = { ...item, ...patch }
  if (updated.action === 'REVIEW' && updated.name?.trim() && updated.type) {
    return { ...updated, action: 'NEW_ASSET', reason: undefined }
  }
  return updated
}
