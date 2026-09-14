import defaultCover from '../../assets/covers/default-editorial-book-cover.png'

/** 统一默认书封：纯 presentation 装饰，绝不是已保存封面或作品事实。 */
export function EditorialCover() {
  return (
    <span className="editorial-cover" aria-hidden="true">
      <img src={defaultCover} alt="" draggable={false} />
    </span>
  )
}
