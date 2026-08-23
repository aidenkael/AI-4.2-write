import type { Candidate, MockWorkbenchService } from '../contracts/ui'
const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
export const mockService: MockWorkbenchService = {
  async simulate<T>(value: T, delay = 650) { await wait(delay); return value },
  async createIdea(content, kind = '场景') { await wait(450); return { id: crypto.randomUUID(), kind, content, note: 'AI 小提示：可以继续发展人物、冲突或氛围。', time: '刚刚', used: false } },
  async generateCandidates(input) {
    await wait(900)
    const items: Candidate[] = [
      { id: 'a', title: '选择揭露真相', body: `让主角回应“${input.slice(0, 18)}”，向盟友坦白已掌握的真相，换取支持，但也引来更大的风险。`, tone: '信任建立 · 风险上升', status: 'candidate' },
      { id: 'b', title: '继续隐藏真相', body: '暂时保守秘密，先观察局势再做决定，但隐瞒可能让盟友产生误解。', tone: '暂时安全 · 信任考验', status: 'candidate' },
      { id: 'c', title: '部分透露试探', body: '只透露一部分信息，试探对方反应，为后续决策争取更多空间。', tone: '谨慎试探 · 保留余地', status: 'candidate' },
    ]
    return items
  },
  async generateProse(prompt) { await wait(900); return `林砚推开那扇半掩的铁门，灰尘在光束中翻涌。\n\n仓库里堆满旧木箱和生锈的机械零件，角落里一只破旧的皮箱吸引了他的注意。${prompt ? `他想起刚才写下的念头：“${prompt}”。` : ''} 箱扣弹开的声音很轻，却让整座仓库仿佛忽然安静下来。` },
}
