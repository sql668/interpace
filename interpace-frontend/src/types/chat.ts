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
  /** 该条消息所属的模式，取值与后端 select_model 对齐 */
  select_model: number
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

/**
 * 面试复盘结果（对应后端 `app/schemas/interview_evaluation_schemas.py`，T8.2 / T8.3）。
 */
export type InterviewEvaluation = {
  id: number
  interview_id: number
  /** 整体表现总结 */
  summary: string
  /** 薄弱知识点 */
  weak_topics: string[]
  /** 改进建议 */
  suggestions: string[]
  /** 来源：0=面试问答文本，1=上传的录音转写 */
  source: 0 | 1
  /** 来源为录音时的资源 ID（可据此回放） */
  resource_id: number | null
  /** 输入规模：问答条数（source=0）或转写分句数（source=1） */
  qa_count: number
  created_at: number
  updated_at: number
}

/** 生成复盘的响应：一定带结果 */
export type InterviewEvaluationGeneratedResponse = {
  message: string
  evaluation: InterviewEvaluation
}

/**
 * 读取复盘的响应：**「还没生成复盘」时 `evaluation` 为 null（HTTP 200，不是 404）**。
 * 后端刻意不用 404 表达这个正常状态——否则每次打开面板都会产生一次错误响应。
 */
export type InterviewEvaluationQueryResponse = {
  message: string
  evaluation: InterviewEvaluation | null
}

/** 录音复盘额外带回转写文本，便于用户核对「AI 听到了什么」 */
export type InterviewEvaluationFromAudioResponse = InterviewEvaluationGeneratedResponse & {
  transcript: string
}

/** 结束面试的响应（T7.8）；already_finished=true 表示之前就结束了（重复点击） */
export type InterviewFinishResponse = {
  message: string
  interview_id: number
  status: number
  interview_duration: number
  qa_count: number
  already_finished: boolean
}

export type UiMessage = {
  id: string
  /** 后端 chat_messages 主键；本地占位消息在收到 start 事件后才拿得到 */
  messageId?: number
  role: 'assistant' | 'user'
  text: string
  createdAt: number
  segments: MessageSegment[]
  /** 助手消息是否仍在等待首个响应片段：为 true 时展示加载动画 */
  pending?: boolean
  status?: number
  interviewId?: number
  /** 该条消息所属的模式，用于在气泡上回显模式标签 */
  selectModel?: number
}
