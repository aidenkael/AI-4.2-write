/**
 * 任务完成提示音（真实生效；尽力而为，失败静默）。
 *
 * 用 WebAudio 合成短提示音，无任何音频资产；浏览器自动播放策略下若
 * AudioContext 被挂起则静默失败——绝不因此影响任务或 UI。
 */
export function playCompletionSound(): void {
  try {
    const Ctor: typeof AudioContext | undefined =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return
    const ctx = new Ctor()
    const now = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(880, now)
    osc.frequency.exponentialRampToValueAtTime(1320, now + 0.15)
    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(0.22, now + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.35)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start(now)
    osc.stop(now + 0.4)
    osc.onended = () => {
      void ctx.close().catch(() => {})
    }
  } catch {
    // 尽力而为：播放失败不影响任何任务
  }
}
