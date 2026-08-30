import type { IllustrationKey } from '../contracts/ui'
// 保持 Vite 可追踪的静态资源 URL，同时让无浏览器加载器的组件烟测可导入 AppStore。
export const defaultIllustrations: Record<IllustrationKey, string> = {
  city: new URL('./city.svg', import.meta.url).href,
  mountains: new URL('./mountains.svg', import.meta.url).href,
  desk: new URL('./desk.svg', import.meta.url).href,
}
export const illustrationLabels: Record<IllustrationKey, string> = { city: '城市主视觉', mountains: '山水与灯塔', desk: '书桌与绿植' }
