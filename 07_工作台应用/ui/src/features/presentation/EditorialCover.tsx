import { editorialIllustrations } from '../../assets/editorialIllustrations'

const covers = [
  editorialIllustrations.worksOverview,
  editorialIllustrations.materials,
  editorialIllustrations.ideasSettings,
  editorialIllustrations.foundationPlanning,
  editorialIllustrations.storyMapReview,
]

/** Stable decoration, never a stored cover or a statement about the story. */
export function EditorialCover({ id }: { id: string }) {
  let hash = 0
  for (let i = 0; i < id.length; i += 1) hash = ((hash << 5) - hash + id.charCodeAt(i)) | 0
  const variant = Math.abs(hash) % (covers.length * 2)
  return <span className={`editorial-cover editorial-cover-v${variant}`} aria-hidden="true">
    <img src={covers[variant % covers.length]} alt="" draggable={false} />
  </span>
}
