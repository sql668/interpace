/**
 * 聊天模式常量。
 *
 * `value` 必须与后端 `app/agent/scene_registry.py` 里的 `SCENE_SPECS` 保持一致：
 * 前端只提交 `select_model`，`agent_name` / `scene` 由后端查注册表决定。
 *
 * 注意：「知识精讲」在学习室和面试间共用 value `1`，两个列表里指向同一个值，
 * 差异只体现在会话的 `session_model` 上。
 */

export type ChatMode = {
  /** 与后端 chat_messages.select_model 对齐 */
  value: number
  /** 界面上展示的模式名 */
  label: string
}

/** 默认模式：没有选择任何模式时提交的 select_model。 */
export const DEFAULT_CHAT_MODE = 0

/** 知识精讲：学习室与面试间共用同一个 select_model。 */
export const KNOWLEDGE_MODE = 1

/** 刷题评测：仅学习室可选。 */
export const QUIZ_MODE = 2

/** 简历优化：仅面试间可选（配「下载 Word」与画像确认卡片）。 */
export const RESUME_MODE = 3

/** 模拟面试：仅面试间可选。 */
export const INTERVIEW_MODE = 4

/** 面试复盘：仅面试间可选。 */
export const EVALUATION_MODE = 5

/** 学习室可选模式。 */
export const STUDY_MODES: ChatMode[] = [
  { value: DEFAULT_CHAT_MODE, label: '快速回答' },
  { value: KNOWLEDGE_MODE, label: '知识精讲' },
  { value: QUIZ_MODE, label: '刷题评测' }
]

/** 面试间可选模式。 */
export const INTERVIEW_MODES: ChatMode[] = [
  { value: DEFAULT_CHAT_MODE, label: '快速回答' },
  { value: RESUME_MODE, label: '简历优化' },
  { value: INTERVIEW_MODE, label: '模拟面试' },
  { value: EVALUATION_MODE, label: '面试复盘' },
  { value: KNOWLEDGE_MODE, label: '知识精讲' }
]

/**
 * 按 value 反查模式，用于历史消息回显模式标签。
 * 两个房间的列表有重叠（0 和 1 是共用的），这里按 value 取第一次命中的那个。
 */
export function findChatMode(value: number): ChatMode | undefined {
  return [...STUDY_MODES, ...INTERVIEW_MODES].find((mode) => mode.value === value)
}
