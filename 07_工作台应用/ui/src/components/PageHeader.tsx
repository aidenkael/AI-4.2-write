import type { ReactNode } from 'react'
export function PageHeader({ title, subtitle, action, art }: { title: string; subtitle: string; action?: ReactNode; art?: string }) {
  return <header className={`page-heading${art ? ' has-art' : ''}`}>
    <div className="page-heading-copy"><h1>{title}</h1><p>{subtitle}</p></div>
    {action ? <div className="page-heading-action">{action}</div> : null}
    {art ? <img className="page-heading-art" src={art} alt="" aria-hidden="true" draggable={false} /> : null}
  </header>
}
