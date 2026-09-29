/**
 * 流式文本「打字机」缓冲器。
 *
 * 后端 SSE 的 delta 到达节奏并不均匀：可能一次吐出几十字，也可能停顿几百毫秒。
 * 若把 delta 直接渲染到界面，视觉上就是一卡一顿的跳变。这里把文本先写入缓冲区，
 * 由 requestAnimationFrame 按帧逐步揭示，并对积压做追赶控制——积压越多、单帧揭示
 * 的字符越多，因此既平滑，又不会明显落后于后端。
 *
 * 用法：push() 追加增量，finish() 收尾（揭示剩余文本并回调全文），
 * flush() 立即揭示全部缓冲内容，cancel() 丢弃缓冲并中止动画。
 */

/** 基础揭示速度（字符/秒）：正常跟得上后端节奏时的观感速度 */
const BASE_CHARS_PER_SECOND = 90

/** 追赶窗口（秒）：无论积压多少，都尽量在这个时间内追平，避免动画明显滞后 */
const CATCH_UP_SECONDS = 0.4

/** 收尾追赶窗口（秒）：流结束后的剩余文本用更快的速度揭示 */
const FINISH_CATCH_UP_SECONDS = 0.22

/** 单帧最多揭示的字符数，避免一次刷出过多造成闪烁 */
const MAX_CHARS_PER_FRAME = 240

/** 单帧最大时间步长（秒）：切换后台标签页后 rAF 间隔会很大，需要封顶 */
const MAX_FRAME_DELTA_SECONDS = 0.1

/** 收尾兜底时长（毫秒）：后台标签页会暂停 rAF，避免流式状态永远不结束 */
const FINISH_FALLBACK_MS = 1000

export type TypewriterStreamOptions = {
  /** 每帧需要揭示的增量文本 */
  onAppend: (delta: string) => void
  /** 剩余文本全部揭示完成时回调，参数为服务端返回的最终全文 */
  onFinish?: (fullText: string) => void
}

export type TypewriterStream = {
  /** 追加一段服务端增量文本 */
  push: (delta: string) => void
  /** 流正常结束：揭示剩余文本，然后回调 onFinish(全文) */
  finish: (fullText: string) => void
  /** 立即揭示全部已缓冲文本并结束动画（保留内容，不回调 onFinish） */
  flush: () => void
  /** 丢弃缓冲并中止动画（用于切换会话、页面卸载等场景） */
  cancel: () => void
}

export function createTypewriterStream(options: TypewriterStreamOptions): TypewriterStream {
  /** 已收到的完整文本 */
  let buffer = ''
  /** 已揭示到 buffer 的下标位置 */
  let revealed = 0
  let frameId: number | null = null
  let fallbackTimer: ReturnType<typeof setTimeout> | null = null
  let lastTimestamp = 0
  /** 是否已收到 finish()，等待把剩余文本揭示完 */
  let finishing = false
  let finishedText = ''
  let closed = false

  const clearFrame = () => {
    if (frameId !== null) {
      cancelAnimationFrame(frameId)
      frameId = null
    }
  }

  const clearTimers = () => {
    clearFrame()
    if (fallbackTimer !== null) {
      clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
  }

  /** 把剩余文本一次性揭示掉 */
  const revealRest = () => {
    if (revealed >= buffer.length) {
      return
    }
    const delta = buffer.slice(revealed)
    revealed = buffer.length
    options.onAppend(delta)
  }

  /** 正常收尾：停止动画并回调全文 */
  const complete = () => {
    if (closed) {
      return
    }
    clearTimers()
    revealRest()
    closed = true
    options.onFinish?.(finishedText || buffer)
  }

  /** 按「基础速度」与「追赶速度」取较大者，得到本帧应揭示的字符数 */
  const resolveStepSize = (pending: number, deltaSeconds: number): number => {
    const catchUpSeconds = finishing ? FINISH_CATCH_UP_SECONDS : CATCH_UP_SECONDS
    const byBaseSpeed = BASE_CHARS_PER_SECOND * deltaSeconds
    const byCatchUp = (pending / catchUpSeconds) * deltaSeconds
    const size = Math.ceil(Math.max(byBaseSpeed, byCatchUp))
    return Math.min(Math.max(size, 1), MAX_CHARS_PER_FRAME, pending)
  }

  const step = (timestamp: number) => {
    frameId = null
    if (closed) {
      return
    }
    // 首帧没有上一帧时间戳，按 60fps 估算
    const elapsed = lastTimestamp
      ? Math.min((timestamp - lastTimestamp) / 1000, MAX_FRAME_DELTA_SECONDS)
      : 1 / 60
    lastTimestamp = timestamp

    const pending = buffer.length - revealed
    if (pending <= 0) {
      if (finishing) {
        complete()
      }
      return
    }

    const size = resolveStepSize(pending, elapsed)
    const delta = buffer.slice(revealed, revealed + size)
    revealed += size
    options.onAppend(delta)

    if (revealed >= buffer.length && finishing) {
      complete()
      return
    }
    schedule()
  }

  function schedule() {
    if (frameId !== null || closed) {
      return
    }
    frameId = requestAnimationFrame(step)
  }

  const push = (delta: string) => {
    if (closed || !delta) {
      return
    }
    buffer += delta
    schedule()
  }

  const finish = (fullText: string) => {
    if (closed || finishing) {
      return
    }
    finishing = true
    // 全文由调用方在 onFinish 中兜底覆盖，这里只负责把已收到的内容揭示完
    finishedText = fullText
    if (revealed >= buffer.length) {
      complete()
      return
    }
    schedule()
    // 后台标签页 rAF 会被暂停，加一个兜底定时器保证流式状态能结束
    fallbackTimer = setTimeout(complete, FINISH_FALLBACK_MS)
  }

  const flush = () => {
    if (closed) {
      return
    }
    clearTimers()
    revealRest()
    closed = true
  }

  const cancel = () => {
    if (closed) {
      return
    }
    clearTimers()
    buffer = ''
    revealed = 0
    closed = true
  }

  return { push, finish, flush, cancel }
}
