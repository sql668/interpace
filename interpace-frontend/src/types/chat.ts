export type SegmentType = 'file' | 'image' | 'audio'

export type MessageSegment = {
  type: SegmentType
  name?: string
  url?: string
  resource_id?: number
}

export type SessionItem = {
  id: number
  session_model: number
  title: string
  created_at: number
}

export type SessionListResponse = {
  page: number
  page_size: number
  total: number
  has_more: boolean
  sessions: SessionItem[]
}

export type SessionRecord = {
  id: number
  status: number
  interview_id?: number
  request_text: string
  response_text: string
  request_segments: MessageSegment[]
  response_segments: MessageSegment[]
  created_at: number
}

export type SessionMessagesResponse = {
  session_id: number
  page: number
  page_size: number
  has_more: boolean
  messages: SessionRecord[]
}

export type InterviewQaItem = {
  question: string
  answer: string
}

export type InterviewDetail = {
  id: number
  session_id: number
  message_id: number
  qa_object: InterviewQaItem[]
  interview_duration: number
  status: number
  created_at: number
  updated_at: number
}

export type UiMessage = {
  id: string
  role: 'assistant' | 'user'
  text: string
  createdAt: number
  segments: MessageSegment[]
  /** 助手消息是否仍在等待首个响应片段：为 true 时展示加载动画 */
  pending?: boolean
  status?: number
  interviewId?: number
}
