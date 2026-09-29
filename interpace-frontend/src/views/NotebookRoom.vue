<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createSession, deleteSession, getSessionMessages, getSessions, updateSessionTitle } from '@/api/chat'
import AppHeader from '@/components/layout/AppHeader.vue'
import SideBar from '@/components/layout/SideBar.vue'
import NotebookEditor from '@/components/notebook/NotebookEditor.vue'
import { tabs } from '@/composables/useRoomShell'
import type { MessageSegment, SessionItem, SessionRecord } from '@/types/chat'
// 笔记本固定使用会话模式 2。
const SESSION_MODEL: 2 = 2

type NoteDocument = {
  title: string
  content: string
}

const route = useRoute()
const router = useRouter()

const activeTab = ref('notebook')
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<number | null>(null)
const loadingSessions = ref(false)
const sessionPage = ref(1)
const sessionPageSize = 20
const sessionHasMore = ref(false)

const notes = ref<Record<string, NoteDocument>>({})

watch(
  () => route.path,
  (path) => {
    const tab = tabs.find((item) => item.path === path)
    if (tab) activeTab.value = tab.key
  },
  { immediate: true }
)

const handleTabClick = async (tabKey: string) => {
  const selectedTab = tabs.find((tab) => tab.key === tabKey)
  if (!selectedTab) return
  activeTab.value = tabKey
  await router.push(selectedTab.path)
}

const ensureNote = (sessionId: number, title = '未命名笔记') => {
  // 本地兜底：保证编辑器总能拿到一个可编辑对象。
  const key = String(sessionId)
  if (!notes.value[key]) {
    notes.value[key] = { title, content: '<p><br></p>' }
  }
}

const activeNote = computed(() => {
  const id = activeSessionId.value
  if (!id) {
    return { title: '未命名笔记', content: '<p>请开始记录你的学习笔记...</p>' }
  }
  const current = notes.value[String(id)]
  if (current) return current
  return { title: '未命名笔记', content: '<p>请开始记录你的学习笔记...</p>' }
})

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const renderSegments = (segments: MessageSegment[]) => {
  // 附件在笔记中以“链接列表”形式落盘，便于后续二次编辑。
  if (!segments.length) return ''
  const lines = segments.map((segment) => {
    const label = segment.name || '未命名附件'
    if (segment.url) {
      return `<li><a href="${escapeHtml(segment.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a></li>`
    }
    return `<li>${escapeHtml(label)}</li>`
  })
  return `<ul>${lines.join('')}</ul>`
}

const mapMessagesToNoteContent = (messages: SessionRecord[]) => {
  // 将聊天记录整理为可编辑的 HTML 初稿，作为笔记初始内容。
  if (!messages.length) {
    return '<p>当前会话暂无聊天记录，可直接开始记录笔记。</p>'
  }
  const sorted = [...messages].sort((a, b) => a.created_at - b.created_at)
  const blocks = sorted.map((item) => {
    const userText = item.request_text ? `<p><strong>用户：</strong>${escapeHtml(item.request_text)}</p>` : ''
    const userSegments = renderSegments(item.request_segments || [])
    const assistantText = item.response_text ? `<p><strong>AI：</strong>${escapeHtml(item.response_text)}</p>` : ''
    const assistantSegments = renderSegments(item.response_segments || [])
    return `${userText}${userSegments}${assistantText}${assistantSegments}`
  })
  return blocks.join('<hr/>')
}

const loadSessionNoteFromMessages = async (sessionId: number, title: string) => {
  // 读取会话消息并生成笔记初稿；上限 10 页避免单次请求过大。
  let page = 1
  const pageSize = 20
  let hasMore = true
  const all: SessionRecord[] = []
  while (hasMore && page <= 10) {
    const data = await getSessionMessages(sessionId, {
      page,
      page_size: pageSize,
      session_model: SESSION_MODEL
    })
    all.push(...data.messages)
    hasMore = data.has_more
    page += 1
  }
  notes.value[String(sessionId)] = {
    title,
    content: mapMessagesToNoteContent(all)
  }
}

const loadSessions = async (reset = false) => {
  if (loadingSessions.value) return
  loadingSessions.value = true
  try {
    if (reset) {
      sessions.value = []
      sessionPage.value = 1
    }
    const data = await getSessions({
      page: sessionPage.value,
      page_size: sessionPageSize,
      session_model: SESSION_MODEL
    })
    sessions.value = reset ? data.sessions : [...sessions.value, ...data.sessions]
    sessionHasMore.value = data.has_more
    sessionPage.value += 1
    const first = sessions.value[0]
    if (!activeSessionId.value && first) {
      activeSessionId.value = first.id
      // 首屏默认把首会话消息转为笔记内容。
      await loadSessionNoteFromMessages(first.id, first.title)
    }
  } finally {
    loadingSessions.value = false
  }
}

const createNewSession = async () => {
  try {
    const promptResult = (await ElMessageBox.prompt('请输入笔记主题标题', '新建笔记', {
      inputValue: '新笔记',
      inputPattern: /.+/,
      inputErrorMessage: '标题不能为空'
    })) as { value: string }
    const result = await createSession({ title: promptResult.value.trim(), session_model: 2 })
    sessions.value.unshift(result.session)
    activeSessionId.value = result.session.id
    await loadSessionNoteFromMessages(result.session.id, result.session.title)
  } catch {
    // 用户取消时不提示
  }
}

const handleSessionClick = async (id: number | string) => {
  const sessionId = Number(id)
  if (Number.isNaN(sessionId)) return
  activeSessionId.value = sessionId
  const target = sessions.value.find((item) => item.id === sessionId)
  await loadSessionNoteFromMessages(sessionId, target?.title ?? '未命名笔记')
}

const editSessionTitle = async (id: number | string) => {
  const sessionId = Number(id)
  const target = sessions.value.find((item) => item.id === sessionId)
  if (!target) return
  try {
    const promptResult = (await ElMessageBox.prompt('请输入新的会话标题', '编辑标题', {
      inputValue: target.title,
      inputPattern: /.+/,
      inputErrorMessage: '标题不能为空'
    })) as { value: string }
    const result = await updateSessionTitle(sessionId, { title: promptResult.value.trim() }, SESSION_MODEL)
    const index = sessions.value.findIndex((item) => item.id === sessionId)
    if (index >= 0) sessions.value[index] = result.session
    const current = notes.value[String(sessionId)]
    if (current) current.title = result.session.title
    ElMessage.success('会话标题已更新')
  } catch {
    // 用户取消时不提示
  }
}

const removeSession = async (id: number | string) => {
  const sessionId = Number(id)
  const target = sessions.value.find((item) => item.id === sessionId)
  if (!target) return
  try {
    await ElMessageBox.confirm(`确认删除会话「${target.title}」吗？`, '删除会话', {
      type: 'warning'
    })
    await deleteSession(sessionId, SESSION_MODEL)
    sessions.value = sessions.value.filter((item) => item.id !== sessionId)
    delete notes.value[String(sessionId)]
    if (activeSessionId.value === sessionId) {
      const next = sessions.value[0]
      activeSessionId.value = next ? next.id : null
      if (next) await loadSessionNoteFromMessages(next.id, next.title)
    }
    ElMessage.success('会话已删除')
  } catch {
    // 用户取消时不提示
  }
}

const updateNoteTitle = (value: string) => {
  const id = activeSessionId.value
  if (!id) return
  const session = sessions.value.find((item) => item.id === id)
  if (session) session.title = value || '未命名笔记'
  ensureNote(id, value || '未命名笔记')
  const note = notes.value[String(id)]
  if (note) {
    note.title = value || '未命名笔记'
  }
}

const updateNoteContent = (value: string) => {
  const id = activeSessionId.value
  if (!id) return
  ensureNote(id)
  const note = notes.value[String(id)]
  if (note) {
    note.content = value
  }
}

onMounted(async () => {
  await loadSessions(true)
  while (sessionHasMore.value && sessions.value.length < 500) {
    await loadSessions(false)
  }
})
</script>

<template>
  <div class="notebook-room">
    <AppHeader :tabs="tabs" :active-tab="activeTab" @tab-click="handleTabClick" />
    <div class="notebook-room__content">
      <SideBar
        :sessions="sessions"
        :active-session-id="activeSessionId ?? ''"
        @create-session="createNewSession"
        @session-click="handleSessionClick"
        @edit-session="editSessionTitle"
        @remove-session="removeSession"
      />
      <NotebookEditor
        :title="activeNote.title"
        :content="activeNote.content"
        @update-title="updateNoteTitle"
        @update-content="updateNoteContent"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.notebook-room {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.notebook-room__content {
  flex: 1;
  min-height: 0;
  display: flex;
}
</style>
