/**
 * 刷题评测相关类型，与后端 `app/schemas/quiz_schemas.py` 对齐。
 *
 * 时间字段是 Unix 秒，与 sessions / chat_messages / notes 保持一致。
 */

/** 卷子状态：0=待作答，1=已提交，2=已评分 */
export type QuizPaperStatus = 0 | 1 | 2

/** 答题用的题目：**不含参考答案**，参考答案只在评分环节用。 */
export type QuizQuestionItem = {
  id: number
  /** 题目序号，从 1 开始 */
  order_index: number
  question: string
  /** 用户作答，未提交时为 null */
  user_answer: string | null
  /** 得分 0-100，未评分时为 null */
  score: number | null
  /** 逐题解析，未评分时为 null */
  analysis: string | null
}

/** 卷子列表项：不含题目。 */
export type QuizPaperItem = {
  id: number
  session_id: number
  /** 入口消息 ID，前端据此把答题卡片挂到对应消息上 */
  message_id: number
  target_job: string | null
  difficulty: string | null
  question_count: number
  status: QuizPaperStatus
  created_at: number
}

/** 卷子详情：在列表项基础上带上题目列表。 */
export type QuizPaperDetail = QuizPaperItem & {
  questions: QuizQuestionItem[]
}

export type QuizPaperListResponse = {
  items: QuizPaperItem[]
  total: number
}

/** 一道题的用户作答。 */
export type QuizAnswerItem = {
  /** 题目序号，与卷子里的 order_index 对应 */
  order_index: number
  /** 用户作答；留空表示放弃这道题 */
  answer: string
}

/** 提交答案请求体；answers 传空数组表示用库里已存的作答重评。 */
export type QuizSubmitPayload = {
  answers: QuizAnswerItem[]
}

/** 提交后的评分结果。 */
export type QuizSubmitResponse = {
  paper_id: number
  /** 提交成功后固定为 2（已评分） */
  status: QuizPaperStatus
  /** 整卷得分，模型没给时为 null */
  total_score: number | null
  weak_topics: string[]
  questions: QuizQuestionItem[]
}
