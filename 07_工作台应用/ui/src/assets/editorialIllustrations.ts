import worksOverview from './illustrations/editorial/01_works_overview_misty_city.webp'
import materials from './illustrations/editorial/02_materials_pages_mountains.webp'
import ideasSettings from './illustrations/editorial/03_ideas_settings_quiet_desk.webp'
import foundationPlanning from './illustrations/editorial/04_foundation_planning_papers_map.webp'
import storyMapReview from './illustrations/editorial/05_storymap_review_map_dawn.webp'
import writingEdge from './illustrations/editorial/06_writing_edge_lighthouse.webp'

// Presentation only: reuse semantic roles in a positioned host; crop or hide at
// narrower widths. Images never determine workspace size or story state.
export const editorialIllustrations = {
  worksOverview,
  materials,
  ideasSettings,
  foundationPlanning,
  storyMapReview,
  writingEdge,
} as const
