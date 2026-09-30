import api from './http'

/**
 * 读取资源内容（图片 / 音频 / 文件），返回 Blob。
 *
 * 为什么用 axios 取 Blob，而不是把接口地址直接塞给 `<img src>`：
 * 资源接口需要 `Authorization: Bearer`，而 `<img>` / `<audio>` 带不了自定义请求头。
 * 取回 Blob 后用 `URL.createObjectURL` 转成临时地址即可正常显示与播放。
 */
export async function fetchResourceBlob(resourceId: number): Promise<Blob> {
  const { data } = await api.get<Blob>(`/resources/${resourceId}/content`, {
    responseType: 'blob'
  })
  return data
}

/**
 * 按 `minio://` 存储路径读取资源内容。
 *
 * 用于只有路径没有资源 ID 的场景——典型是 `users.avatar`，它存的就是路径。
 */
export async function fetchResourceBlobByPath(storagePath: string): Promise<Blob> {
  const { data } = await api.get<Blob>('/resources/content', {
    params: { storage_path: storagePath },
    responseType: 'blob'
  })
  return data
}
