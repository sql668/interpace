/**
 * 画像待确认相关类型，与后端 `app/schemas/profile_proposal_schemas.py` 对齐。
 *
 * 对应 T6.2（决策 D11）：简历解析出的画像信息先给用户确认，确认后才写进画像。
 */

/** 待确认记录状态：0=待确认，1=已确认，2=已忽略 */
export type ProfileProposalStatus = 0 | 1 | 2

export type ProfileProposalItem = {
  id: number
  session_id: number
  /** 来源消息 ID，前端据此把确认卡片挂到对应消息下 */
  message_id: number
  target_job: string | null
  years_experience: string | null
  target_level: string | null
  target_skills: string[]
  weak_topics: string[]
  status: ProfileProposalStatus
  created_at: number
}

export type ProfileProposalListResponse = {
  items: ProfileProposalItem[]
  total: number
}

/** 确认写入的请求体；不传或传空表示「这个字段不动」。 */
export type ProfileProposalConfirmPayload = {
  target_job?: string | null
  years_experience?: string | null
  target_level?: string | null
  target_skills?: string[] | null
  weak_topics?: string[] | null
}

export type ProfileProposalResponse = {
  message: string
  proposal: ProfileProposalItem
}
