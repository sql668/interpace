import api from './http'
import type { InterviewDetail, SessionListResponse, SessionMessagesResponse } from '@/types/chat'

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
