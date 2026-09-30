import api from './http'
import type {
  MemoryCategory,
  ProfileIntentUpdatePayload,
  ProfileMemoryCreatePayload,
  ProfileMemoryItem,
  ProfileMemoryLogItem,
  ProfileMemoryUpdatePayload,
  UserProfileResponse
} from '@/types/userProfile'

// 读取当前用户画像（意图字段 + 能力记忆明细）。没填过时返回空结构，不是 404。
export async function getProfile() {
  const { data } = await api.get<UserProfileResponse>('/profile')
  return data
}

// 更新目标岗位 / 经验年限 / 目标级别；只传要改的字段。
export async function updateProfileIntent(payload: ProfileIntentUpdatePayload) {
  const { data } = await api.put<UserProfileResponse>('/profile', payload)
  return data
}

// 按类别列出能力记忆；不传 category 即全部。
export async function listMemories(category?: MemoryCategory) {
  const { data } = await api.get<ProfileMemoryItem[]>('/profile/memories', {
    params: category === undefined ? {} : { category }
  })
  return data
}

// 手动新增一条能力记忆（自建即生效）。
export async function createMemory(payload: ProfileMemoryCreatePayload) {
  const { data } = await api.post<ProfileMemoryItem>('/profile/memories', payload)
  return data
}

// 修改条目名或掌握程度。
export async function updateMemory(memoryId: number, payload: ProfileMemoryUpdatePayload) {
  const { data } = await api.put<ProfileMemoryItem>(
    `/profile/memories/${memoryId}`,
    payload
  )
  return data
}

// 删除一条记忆：用户有权删掉系统记错的东西。
export async function deleteMemory(memoryId: number) {
  await api.delete(`/profile/memories/${memoryId}`)
}

// 待确认的记忆（T9.9）：自动抽取的条目，批准前不影响对话。
export async function listPendingMemories() {
  const { data } = await api.get<ProfileMemoryItem[]>('/profile/memories/pending')
  return data
}

// 批准一条待确认记忆。
export async function approveMemory(memoryId: number) {
  const { data } = await api.post<ProfileMemoryItem>(
    `/profile/memories/${memoryId}/approve`
  )
  return data
}

// 拒绝一条待确认记忆（后端会删除条目，但保留原文日志）。
export async function rejectMemory(memoryId: number) {
  await api.post(`/profile/memories/${memoryId}/reject`)
}

// 记忆变更日志：回溯系统改过什么、原来是什么。
export async function listMemoryLogs(limit = 20) {
  const { data } = await api.get<ProfileMemoryLogItem[]>('/profile/memory-logs', {
    params: { limit }
  })
  return data
}
