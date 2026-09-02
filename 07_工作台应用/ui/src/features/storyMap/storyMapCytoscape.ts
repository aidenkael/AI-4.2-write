import type { RelationshipGraph } from './storyMapModel'

type ElementData = Record<string, string>

export interface GraphElement {
  data: ElementData
}

/** Convert the read-only map projection into Cytoscape elements without inventing avatar values. */
export function graphElements(model: RelationshipGraph): GraphElement[] {
  return [
    ...model.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.short,
        status: node.status,
        ...(node.avatarImageSrc ? { avatar: node.avatarImageSrc } : {}),
      },
    })),
    ...model.edges.map((edge) => ({
      data: { id: edge.id, source: edge.source, target: edge.target, label: edge.label, status: edge.status },
    })),
  ]
}

/** Image mapping is intentionally limited to nodes that carry a real avatar source. */
export const storyMapStyles = [
  { selector: 'node', style: { label: 'data(label)', 'background-color': '#dce7f8', color: '#172545', 'font-size': 12, 'text-wrap': 'ellipsis', 'text-max-width': '136px', 'text-margin-y': 9, 'text-valign': 'bottom', 'text-halign': 'center', width: 60, height: 60, 'border-color': '#7896c8', 'border-width': 2 } },
  { selector: 'node[avatar]', style: { 'background-image': 'data(avatar)', 'background-fit': 'cover', 'background-image-opacity': 1 } },
  { selector: 'node[status = "future"]', style: { 'border-color': '#6f91df', 'border-width': 3, 'border-style': 'dashed' } },
  { selector: 'edge', style: { label: 'data(label)', 'line-color': '#8fb1ff', 'curve-style': 'bezier', 'font-size': 11, color: '#64728f', 'text-wrap': 'ellipsis', 'text-max-width': '140px' } },
  { selector: 'edge[status = "future"]', style: { 'line-style': 'dashed', 'line-color': '#9aa8c5', color: '#7c89a3' } },
  { selector: ':selected', style: { 'overlay-opacity': 0.15, 'overlay-color': '#2868f7' } },
] as const

export interface MutableGraphElement {
  data(nextData: ElementData): unknown
  removeData(key: string): unknown
}

/** Cytoscape keeps omitted data keys, so optional avatar state needs explicit removal. */
export function replaceGraphElementData(existing: MutableGraphElement, nextData: ElementData): void {
  if (!('avatar' in nextData)) existing.removeData('avatar')
  existing.data(nextData)
}
