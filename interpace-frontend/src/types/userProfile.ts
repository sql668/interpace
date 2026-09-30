/**
 * 用户画像相关类型，与后端 `app/schemas/user_profile_schemas.py` 对齐（T9.3 / T9.4）。
 *
 * 两段结构对应两类字段，来源与可信度完全不同：
 * - `intent`：意图类（用户**想要**什么）
 * - `memories`：能力类明细（用户**会**什么，逐条带掌握程度与来源）
 */

/** 记忆类别：0=技能 1=薄弱点 2=答题方法（L2 用同一张表） */
export type MemoryCategory = 0 | 1 | 2

/** 记忆来源：0=模型推断 1=用户自述 2=简历声明 3=行为证据（权重递增） */
export type MemorySource = 0 | 1 | 2 | 3

export type ProfileIntent = {
  target_job: string | null
  years_experience: string | null
  target_level: string | null
}

export type ProfileMemoryItem = {
  id: number
  category: MemoryCategory
  /** 展示用中文名，如「技能」 */
  category_label: string
  name: string
  /** 内部掌握程度 0-100；界面上只展示 mastery_label */
  mastery: number
  /** 对外只给四档：熟练 / 熟悉 / 了解 / 待加强 */
  mastery_label: string
  source: MemorySource
  /** 展示用中文名，如「答题与面试表现」 */
  source_label: string
  confidence: number
  /** 被证据强化过几次 */
  evidence_count: number
  last_evidence_at: number | null
  /** 1=自动抽取待用户确认（T9.9），这类条目在批准前不影响对话 */
  pending_approval: number
  updated_at: number
}

export type UserProfileResponse = {
  intent: ProfileIntent
  memories: ProfileMemoryItem[]
  /** 兼容字段：提示词注入读的就是这两个扁平列表 */
  target_skills: string[]
  weak_topics: string[]
}

export type ProfileIntentUpdatePayload = {
  target_job?: string | null
  years_experience?: string | null
  target_level?: string | null
}

export type ProfileMemoryCreatePayload = {
  category: MemoryCategory
  name: string
  mastery: number
}

export type ProfileMemoryUpdatePayload = {
  name?: string
  mastery?: number
}

/** 记忆变更日志（T9.9）：用于回答「系统原来记的是什么」 */
export type ProfileMemoryLogItem = {
  id: number
  memory_id: number | null
  category: MemoryCategory
  category_label: string
  name: string
  action: string
  /** 展示用中文，如「已批准」「合并更新」 */
  action_label: string
  /** 变更前的原文快照（JSON 字符串） */
  before_json: string | null
  after_json: string | null
  created_at: number
}

/**
 * 四档掌握程度与内部分值的对应。
 *
 * 用户按「档」思考（「我对这个只是了解」），系统按分数计算，
 * 所以编辑时让用户选档、再映射成分数；展示时永远只显示档，不显示分数。
 */
export const MASTERY_OPTIONS: { label: string; value: number }[] = [
  { label: '待加强', value: 20 },
  { label: '了解', value: 45 },
  { label: '熟悉', value: 70 },
  { label: '熟练', value: 90 }
]

export const CATEGORY_OPTIONS: { label: string; value: MemoryCategory }[] = [
  { label: '技能', value: 0 },
  { label: '薄弱点', value: 1 },
  { label: '答题方法', value: 2 }
]
