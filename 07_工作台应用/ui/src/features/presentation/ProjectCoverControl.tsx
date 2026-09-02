import { Image, RotateCcw } from 'lucide-react'
import { pickAndSetPresentation, resetProjectCover } from '../../bridge/client'
import { useProjectPresentation } from './useProjectPresentation'

export function ProjectCoverControl({ projectId, name, compact = false }: { projectId: string; name: string; compact?: boolean }) {
  const { presentation, reload } = useProjectPresentation(projectId)
  const cover = presentation?.project_cover
  const setCover = async () => { await pickAndSetPresentation({ target: 'cover', project_id: projectId }); await reload() }
  const reset = async () => { await resetProjectCover(projectId); await reload() }
  return <div className={`project-cover ${compact ? 'compact' : ''}`}>
    {cover?.image_src ? <img src={cover.image_src} alt={`${name}封面`}/> : <div className="project-cover-placeholder" aria-label="默认作品封面">Go Write</div>}
    <div className="project-cover-actions"><button onClick={() => void setCover()}><Image /> {cover?.has_custom ? '更换封面' : '设置封面'}</button>{cover?.has_custom && <button onClick={() => void reset()}><RotateCcw /> 恢复默认</button>}</div>
  </div>
}
