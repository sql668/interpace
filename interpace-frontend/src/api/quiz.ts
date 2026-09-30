import api from './http'
import type {
  QuizPaperDetail,
  QuizPaperListResponse,
  QuizSubmitPayload,
  QuizSubmitResponse
} from '@/types/quiz'

// 按会话列出卷子；返回项不含题目，用于把历史消息映射到答题卡片。
export async function getQuizPapersBySession(sessionId: number) {
  const { data } = await api.get<QuizPaperListResponse>('/quiz-papers', {
    params: { session_id: sessionId }
  })
  return data
}

// 获取卷子详情（含题目，不含参考答案）。
export async function getQuizPaperDetail(paperId: number) {
  const { data } = await api.get<QuizPaperDetail>(`/quiz-papers/${paperId}`)
  return data
}

// 提交答案并同步评分；一份卷子只评分一次，重复提交后端返回 409。
export async function submitQuizPaper(paperId: number, payload: QuizSubmitPayload) {
  const { data } = await api.post<QuizSubmitResponse>(
    `/quiz-papers/${paperId}/submissions`,
    payload
  )
  return data
}
