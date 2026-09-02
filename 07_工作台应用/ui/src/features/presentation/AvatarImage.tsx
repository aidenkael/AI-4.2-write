export function AvatarImage({ src, className = '', alt = '' }: { src: string | null | undefined; className?: string; alt?: string }) {
  return src
    ? <img className={`character-avatar-image ${className}`} src={src} alt={alt}/>
    : <span className={`character-avatar-placeholder ${className}`} aria-label={alt || '默认人物头像'} aria-hidden={!alt}>◌</span>
}
