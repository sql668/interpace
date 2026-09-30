import api from './http'
import { fetchResourceBlob } from './resource'
import type { ResumeExportResponse } from '@/types/resume'

// 把某条消息里的「优化后的简历」导出成 Word；后端落成资源后返回下载路径。
export async function exportResume(messageId: number) {
  const { data } = await api.post<ResumeExportResponse>('/resumes/export', {
    message_id: messageId
  })
  return data
}

/**
 * 导出并触发浏览器下载。
 *
 * 两步走的原因：资源接口需要 `Authorization` 头，`<a href>` 带不上，
 * 所以先用 axios 取 Blob，再用临时地址触发下载（与附件下载同一条路）。
 */
export async function downloadResumeWord(messageId: number): Promise<string> {
  const exported = await exportResume(messageId)
  const blob = await fetchResourceBlob(exported.resource_id)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = exported.file_name
  link.click()
  // 下载已触发，回收临时地址，避免内存泄漏
  URL.revokeObjectURL(url)
  return exported.file_name
}
