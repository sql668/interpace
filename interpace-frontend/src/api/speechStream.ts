import { getAccessToken } from './token'

import { env } from '@/config/env'

/**
 * 语音面试的 WebSocket 客户端（T7.7）。
 *
 * 后端契约见 `app/services/speech_stream_service.py` 顶部的消息协议说明。
 * 这里只做「连接 + 收发」，状态机在 `useVoiceInterview` 里。
 *
 * 为什么要用 WebSocket 而不是 fetch：音频要**边说边传**、面试官的话要**边合成边播**，
 * 两边的实时性都要求长连接；HTTP 的请求-响应模型做不到这一点。
 */

/** 后端下发的 JSON 事件 */
export type SpeechEvent =
  | { type: 'ready'; asr_sample_rate: number; tts_sample_rate: number; tts_format: string }
  | { type: 'asr_partial'; text: string }
  | { type: 'asr_final'; text: string }
  | { type: 'reply'; text: string; interview_id: number | null; message_id: number }
  | { type: 'tts_start'; format: string; sample_rate: number }
  | { type: 'tts_subtitle'; text: string; start_ms: number | null; end_ms: number | null; phonemes: unknown[] }
  | { type: 'tts_end' }
  // 演示环境的单场面试时长到点：服务端已自动结束这场面试并会关闭连接（T12.4）。
  | { type: 'interview_timeout'; message: string; max_minutes: number; interview_id: number | null }
  | { type: 'error'; message: string }

export type SpeechStreamHandlers = {
  /** 收到 JSON 事件 */
  onEvent: (event: SpeechEvent) => void
  /** 收到一段 PCM 音频（二进制帧） */
  onAudio: (chunk: ArrayBuffer) => void
  onOpen?: () => void
  onClose?: () => void
  /** 连接层错误（不是后端返回的业务错误，业务错误走 onEvent） */
  onSocketError?: (message: string) => void
}

export type SpeechStreamConnection = {
  sendJson: (payload: Record<string, unknown>) => void
  /** 音频分片：16bit 小端 PCM 字节 */
  sendAudio: (chunk: Uint8Array<ArrayBuffer>) => void
  close: () => void
}

/**
 * 把 HTTP 基地址换算成 WebSocket 地址。
 *
 * 开发环境 `VITE_API_BASE_URL=/api/v1` 是相对路径，走同源（Vite 代理带 `ws: true`）；
 * 生产环境通常是绝对地址，把 http(s) 换成 ws(s) 即可。
 */
export function buildSpeechStreamUrl(sessionId: number, sessionModel: number): string {
  const token = getAccessToken() ?? ''
  const base = env.apiBaseUrl
  const path = `/sessions/${sessionId}/speech/stream?session_model=${sessionModel}&token=${encodeURIComponent(token)}`

  if (/^https?:\/\//i.test(base)) {
    const wsBase = base.replace(/^http/i, 'ws')
    return `${wsBase}${path}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}${base}${path}`
}

export function openSpeechStream(
  sessionId: number,
  sessionModel: number,
  handlers: SpeechStreamHandlers
): SpeechStreamConnection {
  const socket = new WebSocket(buildSpeechStreamUrl(sessionId, sessionModel))
  socket.binaryType = 'arraybuffer'

  socket.onopen = () => handlers.onOpen?.()
  socket.onclose = () => handlers.onClose?.()
  socket.onerror = () => handlers.onSocketError?.('语音通道连接失败')
  socket.onmessage = (message: MessageEvent) => {
    if (typeof message.data === 'string') {
      try {
        handlers.onEvent(JSON.parse(message.data) as SpeechEvent)
      } catch {
        // 单条事件解析失败不该中断整条语音链路
      }
      return
    }
    if (message.data instanceof ArrayBuffer) {
      handlers.onAudio(message.data)
    }
  }

  return {
    sendJson: (payload) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload))
      }
    },
    sendAudio: (chunk) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(chunk)
      }
    },
    close: () => {
      // CONNECTING 状态下直接 close 会抛错，用 try 包住
      try {
        socket.close()
      } catch {
        // 忽略：连接本来就没建立成功
      }
    }
  }
}
