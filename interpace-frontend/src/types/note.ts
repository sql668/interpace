/**
 * 笔记相关类型，与后端 `app/schemas/note_schemas.py` 对齐。
 *
 * 时间字段是 Unix 秒，与 sessions / chat_messages 保持一致。
 */

/** 笔记来源：0=手写，1=来自对话，2=来自复盘 */
export type NoteSourceType = 0 | 1 | 2

/** 笔记列表项：**不含正文**，列表接口只返回这些字段。 */
export type NoteItem = {
  id: number
  title: string
  source_type: NoteSourceType
  /** 来源消息 ID（软引用，源消息被删后可能失效） */
  source_message_id: number | null
  created_at: number
  updated_at: number
}

/** 笔记详情：在列表项基础上带上正文。 */
export type NoteDetail = NoteItem & {
  /** 富文本 HTML */
  content: string
}

export type NoteListResponse = {
  items: NoteItem[]
  total: number
}

/** 创建笔记的请求体；后端对 title / content / source_type 都有默认值。 */
export type NoteCreatePayload = {
  title?: string
  content?: string
  source_type?: NoteSourceType
  source_message_id?: number
}

/** 更新笔记的请求体；只传要改的字段。 */
export type NoteUpdatePayload = {
  title?: string
  content?: string
}

/** 把一条对话消息存入笔记的请求体。 */
export type NoteImportPayload = {
  message_id: number
  title?: string
}

/** 一键存入笔记的响应体；created=false 表示之前已存过。 */
export type NoteImportResponse = {
  message: string
  created: boolean
  note: NoteDetail
}
