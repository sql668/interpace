import api from './http'
import type {
  ProfileProposalConfirmPayload,
  ProfileProposalListResponse,
  ProfileProposalResponse
} from '@/types/profile'

// 按会话列出画像待确认记录；返回项用于把确认卡片挂回历史消息。
export async function getProfileProposalsBySession(sessionId: number) {
  const { data } = await api.get<ProfileProposalListResponse>('/profile-proposals', {
    params: { session_id: sessionId }
  })
  return data
}

// 确认并写入用户画像；传的是用户在卡片上最终认可的值。
export async function confirmProfileProposal(
  proposalId: number,
  payload: ProfileProposalConfirmPayload
) {
  const { data } = await api.post<ProfileProposalResponse>(
    `/profile-proposals/${proposalId}/confirm`,
    payload
  )
  return data
}

// 忽略这条画像信息：不写入画像，只标记为已忽略。
export async function dismissProfileProposal(proposalId: number) {
  const { data } = await api.post<ProfileProposalResponse>(
    `/profile-proposals/${proposalId}/dismiss`
  )
  return data
}
