import { X } from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'

export function FormDialog({ title, children, submitLabel = '保存', onClose, onSubmit }: { title: string; children: ReactNode; submitLabel?: string; onClose(): void; onSubmit(event: FormEvent<HTMLFormElement>): void }) {
  return <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}><form className="dialog form-dialog panel" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(event) => event.stopPropagation()} onSubmit={onSubmit}><header><h2>{title}</h2><button type="button" aria-label="关闭" onClick={onClose}><X/></button></header><div className="form-fields">{children}</div><footer><button type="button" onClick={onClose}>取消</button><button className="primary" type="submit">{submitLabel}</button></footer></form></div>
}
