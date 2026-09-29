import { getAccessToken } from './token'

// 与后端约定的 SSE 消息类型
type StreamEvent =
  | { type: 'start'; message_id: number }
  | { type: 'delta'; text: string }
  | { type: 'done'; response_text: string }
  | { type: 'error'; message: string }

// 发起流式请求所需参数
type StreamChatOptions = {
  sessionId: number
  sessionModel: 0 | 1 | 2
  requestText: string
  selectModel?: number
  provider?: string
  onEvent: (event: StreamEvent) => void
}

// 按 \n\n 拆分 buffer，frames 为完整帧，rest 为剩余未完整部分
function parseSseFrames(buffer: string): { frames: string[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const frames = normalized.split('\n\n')
  const rest = frames.pop() ?? ''
  return { frames, rest }
}

// 获取帧中所有 data: 行，并拼成字符串
function parseSseData(frame: string): string | null {
  const dataLines = frame
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'))
  if (!dataLines.length) {
    return null
  }
  return dataLines.map((line) => line.slice(5).trim()).join('\n')
}

// 读取后端错误信息，优先 message 字段，否则用状态码
async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `stream request failed: ${response.status}`
  try {
    const payload = await response.clone().json()
    if (payload?.message) {
      return String(payload.message)
    }
  } catch {}
  return fallback
}

// 发起流式对话
export async function streamChat(options: StreamChatOptions): Promise<void> {
    const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'
    const baseUrl = base.endsWith('/') ? base.slice(0, -1) : base
    const url = `${baseUrl}/sessions/${options.sessionId}/stream-chat?session_model=${options.sessionModel}`

    const token = getAccessToken()
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        request_text: options.requestText,
        select_model: options.selectModel ?? 0,
        provider: options.provider ?? 'deepseek'
      })
    })

    if (!response.ok || !response.body) {
      throw new Error(await readErrorMessage(response))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    // 持续读取流式数据并触发回调
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { frames, rest } = parseSseFrames(buffer)
      buffer = rest
      for (const frame of frames) {
        const data = parseSseData(frame)
        if (!data) continue
        try {
          options.onEvent(JSON.parse(data) as StreamEvent)
        } catch {
          // 忽略异常帧，避免中断整个流
        }
      }
    }
}
