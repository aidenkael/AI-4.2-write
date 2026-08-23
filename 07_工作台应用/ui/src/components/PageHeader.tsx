import type { ReactNode } from 'react'
export function PageHeader({ title, subtitle, action, art }: { title: string; subtitle: string; action?: ReactNode; art?: string }) {
  return <header className="page-heading" style={art ? { backgroundImage: `linear-gradient(90deg,#fff 28%,rgba(255,255,255,.54)),url(${art})` } : undefined}><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</header>
}
