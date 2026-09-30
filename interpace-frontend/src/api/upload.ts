
import api from './http'

/** 上传接口返回的文档解析摘要；只有 PDF / Word / 纯文本会有。 */
export type UploadParseInfo = {
  ok: boolean
  char_count: number
  suspected_scanned: boolean
  message: string
}

/** 后端 UploadResponse 的对应类型。 */
export type UploadResponse = {
  message: string
  resource_id: number
  file_path: string
  file_hash: string
  resource_type: number
  storage_scene: number
  upload_purpose: number
  expire_time: string | null
  is_deduplicated: boolean
  /** 非文档类型（图片 / 音频）为 null */
  parse: UploadParseInfo | null
}

/** 上传用途：0 普通资源，1 用户头像 */
export const UPLOAD_PURPOSE_GENERAL = 0
export const UPLOAD_PURPOSE_AVATAR = 1

/** 存储场景：0 长过期，1 短过期，2 仅提取，3 永久 */
export const STORAGE_SCENE_LONG = 0
export const STORAGE_SCENE_PERMANENT = 3

type UploadOptions = {
  storageScene?: number
  uploadPurpose?: number
}

/** 通用上传：返回后端原始响应（含文档解析结果）。 */
export async function uploadFile(
  file: File,
  options: UploadOptions = {}
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('upload_purpose', String(options.uploadPurpose ?? UPLOAD_PURPOSE_GENERAL))
  formData.append('storage_scene', String(options.storageScene ?? STORAGE_SCENE_LONG))

  // 注意：此接口需要认证，api 实例会自动附加 Token
  const { data } = await api.post<UploadResponse>('/upload/file', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  return data
}

/**
 * 上传用户头像。
 *
 * - `upload_purpose=1`：后端只在「图片 + 头像用途」时才回写 `users.avatar`；
 * - `storage_scene=3`：头像要永久存储——默认的 0 是「长过期」（30 天），
 *   到期会被资源清理服务回收，头像对象就没了。
 *
 * @param file 头像文件对象
 */
export async function uploadAvatar(file: File): Promise<UploadResponse> {
  return uploadFile(file, {
    uploadPurpose: UPLOAD_PURPOSE_AVATAR,
    storageScene: STORAGE_SCENE_PERMANENT
  })
}
