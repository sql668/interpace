
import api from './http'

/**
 * 上传用户头像
 * @param file 头像文件对象
 */
export async function uploadAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  // 注意：此接口需要认证，api 实例会自动附加 Token
  const { data } = await api.post<{ message: string; avatar_url: string }>(
    '/upload/file',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
  )
  return data
}
