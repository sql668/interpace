import api from './http'
import type {
  InterviewDetail,
  InterviewEvaluationFromAudioResponse,
  InterviewEvaluationGeneratedResponse,
  InterviewEvaluationQueryResponse,
  InterviewFinishResponse,
  SessionListResponse,
  SessionMessagesResponse
} from '@/types/chat'

// 会话列表：按会话模式（学习/面试/笔记）分页查询。
export async function getSessions(params: { page: number; page_size: number; session_model: 0 | 1 | 2 }) {
  const { data } = await api.get<SessionListResponse>('/sessions', { params })
  return data
}

// 创建会话主题。
export async function createSession(payload: { title: string; session_model: number }) {
  const { data } = await api.post<{ message: string; session: SessionListResponse['sessions'][number] }>(
    '/sessions',
    payload
  )
  return data
}

// 编辑会话标题；后端会校验 session_model 与会话归属。
export async function updateSessionTitle(
  sessionId: number,
  payload: { title: string },
  sessionModel: 0 | 1 | 2
) {
  const { data } = await api.put<{ message: string; session: SessionListResponse['sessions'][number] }>(
    `/sessions/${sessionId}`,
    payload,
    { params: { session_model: sessionModel } }
  )
  return data
}

// 删除会话，并联动删除该会话的聊天消息/面试记录/资源。
export async function deleteSession(sessionId: number, sessionModel: 0 | 1 | 2) {
  const { data } = await api.delete<{
    message: string
    session_id: number
    deleted_messages: number
    deleted_interviews: number
    deleted_resources: number
    deleted_quizzes: number
  }>(`/sessions/${sessionId}`, { params: { session_model: sessionModel } })
  return data
}

// 按会话分页拉取聊天记录（正文 + 附件段）。
export async function getSessionMessages(
  sessionId: number,
  params: { page: number; page_size: number; session_model: 0 | 1 | 2 }
) {
  const { data } = await api.get<SessionMessagesResponse>(`/sessions/${sessionId}/messages`, { params })
  return data
}

// 面试详情：用于 status=1 的“面试卡片”点击后弹窗展示。
export async function getInterviewDetail(interviewId: number) {
  const { data } = await api.get<InterviewDetail>(`/interviews/${interviewId}`)
  return data
}

// 结束一场模拟面试（T7.8）：幂等，重复调用只是 already_finished=true。
export async function finishInterview(interviewId: number) {
  const { data } = await api.post<InterviewFinishResponse>(
    `/interviews/${interviewId}/finish`
  )
  return data
}

// 读取已生成的面试复盘；没生成过后端返回 200 + evaluation=null（不是 404）。
export async function getInterviewEvaluation(interviewId: number) {
  const { data } = await api.get<InterviewEvaluationQueryResponse>(
    `/interviews/${interviewId}/evaluations`
  )
  return data
}

// 按面试记录里的问答生成复盘（重复调用会按最新问答重新生成）。
export async function generateInterviewEvaluation(interviewId: number) {
  const { data } = await api.post<InterviewEvaluationGeneratedResponse>(
    `/interviews/${interviewId}/evaluations`
  )
  return data
}

// 用上传的面试录音生成复盘（T8.3）：后端负责转写，响应带回转写文本。
export async function generateInterviewEvaluationFromAudio(
  interviewId: number,
  resourceId: number
) {
  const { data } = await api.post<InterviewEvaluationFromAudioResponse>(
    `/interviews/${interviewId}/evaluations/from-audio`,
    { resource_id: resourceId },
    // 录音转写 + 复盘比普通请求慢得多，单独放宽超时（默认 10 秒会直接超时）
    { timeout: 180000 }
  )
  return data
}

// 停止正在生成的流式回答；重复调用是幂等的，流已结束时调用也不报错。
export async function stopStreamChat(sessionId: number, messageId: number) {
  const { data } = await api.post<{
    message: string
    message_id: number
    first_request: boolean
  }>(`/sessions/${sessionId}/stream-chat/stop`, { message_id: messageId })
  return data
}
