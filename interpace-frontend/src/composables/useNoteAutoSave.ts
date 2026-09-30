import { ref } from 'vue'
import type { NoteUpdatePayload } from '@/types/note'
import { resolveErrorMessage } from '@/utils/errorMessage'

/** 保存状态：idle 无待提交 / pending 已攒改动等防抖 / saving 请求中 / saved 已保存 / error 失败 */
export type NoteSaveStatus = 'idle' | 'pending' | 'saving' | 'saved' | 'error'

type UseNoteAutoSaveOptions = {
  /** 真正落库的动作，由页面传入（通常是 api/note 的 updateNote） */
  save: (noteId: number, payload: NoteUpdatePayload) => Promise<void>
  /** 防抖时长，默认 1000ms */
  delay?: number
  /** 保存失败时回调，页面用它提示用户 */
  onError?: (message: string) => void
}

/**
 * 笔记自动保存：防抖提交 + 串行化 + 可立即冲刷。
 *
 * 三个要点（对应 D5 的结论）：
 * 1. **防抖**：停止输入 delay 毫秒后才提交，避免每敲一个字发一次请求。
 * 2. **串行化**：同一时刻只允许一个保存请求在飞，后来的改动排队等它回来再发。
 *    否则快速编辑会产生多个并发 PUT，网络乱序时后发的先落、先发的后落，
 *    用户看到的就是自己改的内容被「回滚」了。
 * 3. **待提交内容按笔记分组**：切到另一篇笔记时，A 的改动不会被写进 B。
 *
 * 页面负责在「切换笔记 / 组件卸载 / 页面隐藏」时调用 `flush()`——
 * 只靠防抖的话，用户改完立刻切走就会丢掉最后一次改动。
 */
export function useNoteAutoSave(options: UseNoteAutoSaveOptions) {
  const delay = options.delay ?? 1000
  const status = ref<NoteSaveStatus>('idle')

  // noteId -> 待提交的字段（合并同一篇笔记的多次编辑）
  const pendingByNote = new Map<number, NoteUpdatePayload>()
  let timer: ReturnType<typeof setTimeout> | null = null
  let pumping = false

  const clearTimer = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  const pump = async () => {
    // 已有请求在飞：等它结束后自己会继续消费队列，这里直接返回。
    if (pumping) return
    pumping = true
    try {
      while (pendingByNote.size > 0) {
        const entry = pendingByNote.entries().next().value as
          | [number, NoteUpdatePayload]
          | undefined
        if (!entry) break
        const [noteId, payload] = entry
        // 先摘出来再发请求：即使中途又来了新改动，也不会重复提交这一份。
        pendingByNote.delete(noteId)

        status.value = 'saving'
        try {
          await options.save(noteId, payload)
          status.value = pendingByNote.size > 0 ? 'pending' : 'saved'
        } catch (error) {
          // 失败就把改动放回队列（后攒的改动优先），状态置为 error；
          // 下一次 schedule / flush 会重试，不做自动轮询以免后端不可用时打爆。
          const newer = pendingByNote.get(noteId) ?? {}
          pendingByNote.set(noteId, { ...payload, ...newer })
          status.value = 'error'
          options.onError?.(resolveErrorMessage(error, '笔记保存失败'))
          break
        }
      }
    } finally {
      pumping = false
    }
  }

  /** 记下一批改动，重置防抖计时。 */
  const schedule = (noteId: number, payload: NoteUpdatePayload) => {
    const previous = pendingByNote.get(noteId) ?? {}
    pendingByNote.set(noteId, { ...previous, ...payload })
    status.value = 'pending'
    clearTimer()
    timer = setTimeout(() => {
      timer = null
      void pump()
    }, delay)
  }

  /** 立即提交待保存内容：切换笔记 / 组件卸载 / 页面隐藏时调用。 */
  const flush = () => {
    clearTimer()
    void pump()
  }

  /** 丢弃某篇笔记的待提交内容（例如它刚被删除，再提交只会拿到 404）。 */
  const drop = (noteId: number) => {
    pendingByNote.delete(noteId)
    if (pendingByNote.size === 0) {
      clearTimer()
      status.value = 'idle'
    }
  }

  /** 复位状态提示，用于切换笔记时清掉上一篇留下的「已保存 / 失败」。 */
  const resetStatus = () => {
    status.value = pendingByNote.size > 0 ? 'pending' : 'idle'
  }

  return { status, schedule, flush, drop, resetStatus }
}
