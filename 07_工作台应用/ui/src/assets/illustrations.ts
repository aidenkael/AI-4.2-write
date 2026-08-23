import city from './city.svg'
import mountains from './mountains.svg'
import desk from './desk.svg'
import type { IllustrationKey } from '../contracts/ui'
export const defaultIllustrations: Record<IllustrationKey, string> = { city, mountains, desk }
export const illustrationLabels: Record<IllustrationKey, string> = { city: '迷雾之城主视觉', mountains: '山水与灯塔', desk: '书桌与绿植' }
