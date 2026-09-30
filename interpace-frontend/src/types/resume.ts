/** 简历导出相关类型，与后端 `app/schemas/resume_schemas.py` 对齐（T6.4）。 */

export type ResumeExportResponse = {
  resource_id: number
  /** 建议的下载文件名 */
  file_name: string
  content_type: string
  /** 下载路径，如 /resources/12/content */
  download_path: string
  /** 相同内容之前导出过时为 true（复用旧资源） */
  reused: boolean
}
