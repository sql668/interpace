/**
 * 运行时能力开关，与后端 `app/schemas/runtime_config_schemas.py` 对齐。
 *
 * 为什么要有这个接口，而不是前端自己按环境变量判断：
 * 开关的唯一事实来源是后端的 `config/demo_limits.json`（可热改）。
 * 前端再维护一份构建期环境判断，两边迟早不一致——最典型的坏结果就是
 * 「按钮显示着，点了连不上」。
 */

/** 当前环境开放的功能。 */
export type RuntimeFeatures = {
  /** 是否开放语音面试；false 时前端不显示「语音面试」入口 */
  voice_interview: boolean
  /** 是否开放附件上传；false 时前端不显示「+ 附件」入口 */
  file_upload: boolean
}

/** 给用户看的提示文案。 */
export type RuntimeNotice = {
  /** 环境横幅文案；空串表示不用展示 */
  banner_text: string
}

export type RuntimeConfig = {
  /** 当前运行环境：development / demo / test / production */
  app_env: string
  /** 当前环境是否受演示配额约束 */
  quota_enforced: boolean
  features: RuntimeFeatures
  /** 单场模拟面试时长上限（分钟）；0 表示不限 */
  interview_max_minutes: number
  notice: RuntimeNotice
  /** 当前生效的配额数值；未启用配额时为 null。首页的"演示环境限制"直接用这份数据 */
  limits: RuntimeLimits | null
}

/** 当前生效的配额数值（只在演示环境有值）。 */
export type RuntimeLimits = {
  /** 每个 IP 累计可消耗的 token 总量 */
  tokens_per_ip: number
  turns_per_day: number
  quizzes_per_day: number
  evaluations_per_day: number
  voice_minutes_per_day: number
  max_turns_per_session: number
  max_sessions: number
  max_notes: number
}
