import { Plus, X } from 'lucide-react'
import { displayLabel, type RelationOption } from './relationSelectors'

/**
 * 作者面小型关联选择器：标签 + 已选 chips（×移除）+ 下拉“添加关联…”。
 * 内部只存稳定 ref；可见文本永远是记录名称，绝不渲染 ref。
 */
export function RelationSelector({
  label, options, selected, onChange, excludeSelf,
}: {
  label: string
  options: RelationOption[]
  selected: string[]
  onChange(next: string[]): void
  /** 排除与被编辑记录自身同 ref 的选项（避免自环）。 */
  excludeSelf?: string | null
}) {
  const selectedSet = new Set(selected)
  const byRef = new Map(options.map((option) => [option.ref, option]))
  const available = options.filter(
    (option) => !selectedSet.has(option.ref) && option.ref !== excludeSelf,
  )
  return (
    <div className="relation-selector">
      <span className="relation-selector-label">{label}</span>
      <div className="relation-selector-chips">
        {selected.map((ref) => {
          const option = byRef.get(ref)
          return (
            <span className="relation-chip" key={ref}>
              {option ? displayLabel(option) : '（记录已失效，请移除）'}
              {option?.status === 'future' && <em className="relation-chip-status">规划中</em>}
              <button aria-label={`移除关联 ${option ? displayLabel(option) : ref}`} onClick={() => onChange(selected.filter((item) => item !== ref))}>
                <X />
              </button>
            </span>
          )
        })}
        <select
          aria-label={`添加关联：${label}`}
          value=""
          onChange={(event) => {
            const ref = event.target.value
            if (!ref) return
            onChange([...selected, ref])
          }}
        >
          <option value="">{available.length ? '添加关联…' : '暂无可添加记录'}</option>
          {available.map((option) => (
            <option key={option.ref} value={option.ref}>
              {displayLabel(option)}{option.status === 'future' ? '（规划中）' : ''}
            </option>
          ))}
        </select>
        {selected.length === 0 && available.length === 0 && <Plus aria-hidden="true" />}
      </div>
    </div>
  )
}
