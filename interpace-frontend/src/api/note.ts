import api from './http'
import type {
  NoteCreatePayload,
  NoteDetail,
  NoteImportPayload,
  NoteImportResponse,
  NoteListResponse,
  NoteUpdatePayload
} from '@/types/note'

// 分页获取笔记列表，按最近更新倒序；返回项不含正文。
export async function getNotes(params: { limit?: number; offset?: number }) {
  const { data } = await api.get<NoteListResponse>('/notes', { params })
  return data
}

// 创建笔记。
export async function createNote(payload: NoteCreatePayload) {
  const { data } = await api.post<NoteDetail>('/notes', payload)
  return data
}

// 获取笔记详情（含正文）。
export async function getNoteDetail(noteId: number) {
  const { data } = await api.get<NoteDetail>(`/notes/${noteId}`)
  return data
}

// 更新笔记；只传要改的字段，未传的保持原值。
export async function updateNote(noteId: number, payload: NoteUpdatePayload) {
  const { data } = await api.put<NoteDetail>(`/notes/${noteId}`, payload)
  return data
}

// 删除笔记；后端返回 204，没有响应体。
export async function deleteNote(noteId: number) {
  await api.delete(`/notes/${noteId}`)
}

// 把一条对话消息存入笔记；同一条消息重复调用是幂等的（返回 created=false）。
export async function importNoteFromMessage(payload: NoteImportPayload) {
  const { data } = await api.post<NoteImportResponse>('/notes/import', payload)
  return data
}
