import { ref } from 'vue'
import { streamChat } from '@/api/streamChat'
import { stopStreamChat } from '@/api/chat'
import { DEFAULT_CHAT_MODE } from '@/constants/chat-modes'
import type { MessageSegment } from '@/types/chat'
import { createTypewriterStream, type TypewriterStream } from '@/utils/typewriterStream'

// 用于写入流式消息内容的接口
type PendingWriter = {
  appendDelta: (delta: string) => void // 追加流式响应内容
  finish: (fullText: string) => void // 流式响应结束时调用
  cancel: () => void // 流未正常结束（出错或被打断）时调用，用于收尾占位状态
  setMessageId?: (messageId: number) => void // 后端返回消息ID时回调，供占位消息记录真实ID
  // 后端在 done 事件里附带的结构化产物（题库 / 画像 / 面试记录）：
  // 各房间按需取用，让卡片当场出现，不用等刷新。
  setResult?: (result: StreamResultIds) => void
}

// done 事件里可能带回来的结构化产物 ID
export type StreamResultIds = {
  quizPaperId: number | null
  profileProposalId: number | null
  interviewId: number | null
}

// useSessionStreamSender 选项参数类型
type UseSessionStreamSenderOptions = {
  sessionModel: 0 | 1 | 2 // 会话模型类型
  getActiveSessionId: () => number | null // 获取当前会话ID
  // 生成待发送消息的写入器；segments 是本次携带的附件段
  createPending: (text: string, sessionId: number, segments: MessageSegment[]) => PendingWriter
  syncAfterDone?: (sessionId: number) => Promise<void> // 可选，消息发送完触发同步
  onError?: (message: string) => void // 可选，错误时回调
}

// 用于发送聊天流式消息的逻辑复用 Hook
export function useSessionStreamSender(options: UseSessionStreamSenderOptions) {
  // 标记当前是否处于发送中
  const sending = ref(false)
  // 记录当前会话的流请求代号，自增用于中止控制
  const streamEpoch = ref(0)
  // 当前正在播放的打字机缓冲器，用于中止时停止动画
  let activeTypewriter: TypewriterStream | null = null
  // 当前占位消息的写入器，用于中止时收尾等待状态
  let activePending: PendingWriter | null = null
  // 当前流请求的中断控制器，用于真正掐断底层 fetch
  let activeController: AbortController | null = null
  // 当前流的 message_id 与会话ID：停止时要拿它们去调后端的停止接口
  let activeMessageId: number | null = null
  let activeSessionId: number | null = null

  // 停止当前激活的流：通知后端 + 掐断本地请求 + 停掉打字机与等待状态。
  // 不再只靠自增 epoch 丢弃回调——那样网络请求会在后台把整个流读完，后端仍继续生成。
  const stopActiveStream = () => {
    streamEpoch.value += 1
    sending.value = false
    activeTypewriter?.cancel()
    activeTypewriter = null
    activePending?.cancel()
    activePending = null

    const controller = activeController
    const messageId = activeMessageId
    const sessionId = activeSessionId
    activeController = null
    activeMessageId = null
    activeSessionId = null

    // 先通知后端停止（双保险里的显式那一路），再掐断本地 fetch。
    // 停止接口失败不影响「本地已经停下」这个事实，所以不 await、也不弹错。
    if (sessionId !== null && messageId !== null) {
      void stopStreamChat(sessionId, messageId).catch(() => undefined)
    }
    controller?.abort()
  }

  // 发送流式请求；selectModel 决定后端走哪个 Agent / 场景，由各房间在发送时传入。
  const send = async (
    text: string,
    selectModel: number = DEFAULT_CHAT_MODE,
    segments: MessageSegment[] = []
  ) => {
    const sessionId = options.getActiveSessionId()
    // 未选中会话或已有请求在发送中，直接返回
    if (!sessionId || sending.value) {
      return
    }

    // 标记当前请求的 epoch，确保流回调只响应最新的请求
    const requestEpoch = streamEpoch.value + 1
    streamEpoch.value = requestEpoch
    sending.value = true

    // 新建中断控制器并记下本次流的归属，停止时要靠它们收尾
    const controller = new AbortController()
    activeController = controller
    activeSessionId = sessionId
    activeMessageId = null

    // 创建“占位消息”写入控制器
    const pending = options.createPending(text, sessionId, segments)
    activePending = pending

    // 上一轮的打字机如果还在收尾，先让它把缓冲内容说完，避免两条流交叉
    activeTypewriter?.flush()

    // 打字机缓冲：把到达节奏不均匀的 SSE 增量平滑成逐帧揭示的文本
    const typewriter = createTypewriterStream({
      onAppend: (delta) => pending.appendDelta(delta),
      onFinish: (fullText) => pending.finish(fullText)
    })
    activeTypewriter = typewriter

    try {
      await streamChat({
        sessionId,
        sessionModel: options.sessionModel,
        requestText: text,
        selectModel,
        segments,
        signal: controller.signal,
        onEvent: (event) => {
          // 非本轮请求或会话已变化时跳过，防止旧流回调串写
          if (requestEpoch !== streamEpoch.value || options.getActiveSessionId() !== sessionId) {
            return
          }
          if (event.type === 'start') {
            // 记下后端的消息ID，停止接口要靠它定位这次生成
            activeMessageId = event.message_id
            // 同时告诉占位消息，这样「存入笔记」等操作不用等刷新就能拿到 ID
            pending.setMessageId?.(event.message_id)
          }
          if (event.type === 'delta') {
            typewriter.push(event.text || '')
          }
          if (event.type === 'done') {
            typewriter.finish(event.response_text || '')
            pending.setResult?.({
              quizPaperId: event.quiz_paper_id ?? null,
              profileProposalId: event.profile_proposal_id ?? null,
              interviewId: event.interview_id ?? null
            })
          }
          if (event.type === 'error') {
            // 出错时保留已收到的内容，一次性补满显示
            typewriter.flush()
            pending.cancel()
            options.onError?.(event.message || '流式请求失败')
          }
        }
      })
    } catch (error) {
      const err = error as Error
      // 只处理本轮请求的错误
      if (requestEpoch === streamEpoch.value) {
        typewriter.flush()
        pending.cancel()
        options.onError?.(err.message || '流式请求失败')
      }
    } finally {
      // 不是当前流，直接返回避免重入
      if (requestEpoch !== streamEpoch.value) {
        return
      }
      sending.value = false
      // 本轮正常收尾：清掉归属，避免停止逻辑误伤下一次请求
      if (activeController === controller) {
        activeController = null
        activeMessageId = null
        activeSessionId = null
      }
      // 当前会话仍是原会话，且定义了同步方法时，完成后同步对话
      if (options.getActiveSessionId() === sessionId && options.syncAfterDone) {
        await options.syncAfterDone(sessionId)
      }
    }
  }

  // 导出 sending 标记、停止流和发送主逻辑
  return {
    sending,
    stopActiveStream,
    send
  }
}
