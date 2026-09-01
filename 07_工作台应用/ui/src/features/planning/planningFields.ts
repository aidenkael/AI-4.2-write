/**
 * `foreshadowing_setup_payoff` was an early StoryPlan-only alias for the
 * established chapter-outline `foreshadowing` field. Keep old outlines
 * readable, but make every subsequent author save use the canonical field.
 */
export function normalizeChapterForeshadowing(outline: Record<string, unknown>): unknown {
  const canonical = outline.foreshadowing
  if (Array.isArray(canonical) ? canonical.length > 0 : typeof canonical === 'string' && canonical.trim()) return canonical
  return outline.foreshadowing_setup_payoff
}
