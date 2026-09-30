<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createNote, deleteNote, getNoteDetail, getNotes, updateNote } from '@/api/note'
import AppHeader from '@/components/layout/AppHeader.vue'
import SideBar from '@/components/layout/SideBar.vue'
import NotebookEditor from '@/components/notebook/NotebookEditor.vue'
import { useNoteAutoSave, type NoteSaveStatus } from '@/composables/useNoteAutoSave'
import { tabs } from '@/constants/nav-tabs'
import type { NoteDetail, NoteItem } from '@/types/note'

const NOTE_PAGE_SIZE = 50
/** 空笔记正文：wangEditor 用空段落表示「没有内容」 */
const EMPTY_NOTE_CONTENT = '<p><br></p>'
const FALLBACK_TITLE = '未命名笔记'

const route = useRoute()
const router = useRouter()

const activeTab = ref('notebook')
// 左侧列表（不含正文）与当前打开的笔记详情
const notes = ref<NoteItem[]>([])
const activeNoteId = ref<number | null>(null)
const activeNote = ref<NoteDetail | null>(null)
const loadingNotes = ref(false)
const noteOffset = ref(0)
const hasMoreNotes = ref(false)

// ---- 自动保存：防抖 + 切换/卸载/页面隐藏时冲刷 + 请求串行化（见 D5）----
const {
  status: saveStatus,
  schedule: scheduleSave,
  flush: flushSave,
  drop: dropSave,
  resetStatus: resetSaveStatus
} = useNoteAutoSave({
  save: async (noteId, payload) => {
    const updated = await updateNote(noteId, payload)
    // 只同步左侧列表的标题，**不用服务端返回覆盖 activeNote**：
    // 用户很可能已经在继续输入，覆盖会把新输入顶掉。
    const index = notes.value.findIndex((item) => item.id === noteId)
    if (index >= 0) {
      notes.value[index] = {
        ...notes.value[index],
        title: updated.title,
        updated_at: updated.updated_at
      }
    }
  },
  onError: (message) => ElMessage.error(message)
})

const saveStatusText = computed(() => {
  const textByStatus: Record<NoteSaveStatus, string> = {
    idle: '',
    pending: '待保存…',
    saving: '保存中…',
    saved: '已保存',
    error: '保存失败，继续编辑会自动重试'
  }
  return activeNote.value ? textByStatus[saveStatus.value] : ''
})

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

// ---- 列表与详情 ----
const openNote = async (noteId: number) => {
  if (noteId === activeNoteId.value) return
  // 切走之前先把上一篇的待提交改动送出去，否则防抖还没到点就丢了
  flushSave()
  activeNoteId.value = noteId
  resetSaveStatus()
  activeNote.value = await getNoteDetail(noteId)
}

const loadNotes = async (reset = false) => {
  if (loadingNotes.value) return
  loadingNotes.value = true
  try {
    if (reset) {
      notes.value = []
      noteOffset.value = 0
    }
    const data = await getNotes({ limit: NOTE_PAGE_SIZE, offset: noteOffset.value })
    notes.value = reset ? data.items : [...notes.value, ...data.items]
    noteOffset.value += data.items.length
    hasMoreNotes.value = notes.value.length < data.total
    const first = notes.value[0]
    if (!activeNoteId.value && first) {
      await openNote(first.id)
    }
  } finally {
    loadingNotes.value = false
  }
}

// ---- 增删改 ----
const createNewNote = async () => {
  try {
    const promptResult = (await ElMessageBox.prompt('请输入笔记标题', '新建笔记', {
      inputValue: '新笔记',
      inputPattern: /.+/,
      inputErrorMessage: '标题不能为空'
    })) as { value: string }
    flushSave()
    const created = await createNote({
      title: promptResult.value.trim(),
      content: EMPTY_NOTE_CONTENT
    })
    notes.value = [created, ...notes.value]
    activeNoteId.value = created.id
    activeNote.value = created
    resetSaveStatus()
  } catch {
    // 用户取消时不提示
  }
}

const editNoteTitle = async (id: number | string) => {
  const noteId = Number(id)
  const target = notes.value.find((item) => item.id === noteId)
  if (!target) return
  try {
    const promptResult = (await ElMessageBox.prompt('请输入新的笔记标题', '编辑标题', {
      inputValue: target.title,
      inputPattern: /.+/,
      inputErrorMessage: '标题不能为空'
    })) as { value: string }
    const updated = await updateNote(noteId, { title: promptResult.value.trim() })
    const index = notes.value.findIndex((item) => item.id === noteId)
    if (index >= 0) notes.value[index] = { ...notes.value[index], title: updated.title }
    if (activeNoteId.value === noteId && activeNote.value) {
      activeNote.value = { ...activeNote.value, title: updated.title }
    }
  } catch {
    // 用户取消时不提示
  }
}

const removeNote = async (id: number | string) => {
  const noteId = Number(id)
  const target = notes.value.find((item) => item.id === noteId)
  if (!target) return
  try {
    await ElMessageBox.confirm(`确认删除笔记「${target.title}」吗？`, '删除笔记', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    // 先丢弃待提交内容，否则删完还会补发一次保存请求、拿到 404
    dropSave(noteId)
    await deleteNote(noteId)
    notes.value = notes.value.filter((item) => item.id !== noteId)
    if (activeNoteId.value === noteId) {
      activeNoteId.value = null
      activeNote.value = null
      const next = notes.value[0]
      if (next) await openNote(next.id)
    }
    ElMessage.success('笔记已删除')
  } catch {
    // 用户取消时不提示
  }
}

// ---- 编辑器输入：先更新本地，再交给自动保存 ----
const handleTitleChange = (value: string) => {
  const note = activeNote.value
  // 正在切换笔记（详情还没回来）时忽略，避免把上一篇的内容写到新笔记上
  if (!note || note.id !== activeNoteId.value) return
  const title = value || FALLBACK_TITLE
  activeNote.value = { ...note, title }
  const index = notes.value.findIndex((item) => item.id === note.id)
  if (index >= 0) notes.value[index] = { ...notes.value[index], title }
  scheduleSave(note.id, { title })
}

const handleContentChange = (value: string) => {
  const note = activeNote.value
  if (!note || note.id !== activeNoteId.value) return
  // wangEditor 在 setHtml 之后也会触发一次 onChange，值没变就跳过，避免自我循环
  if (note.content === value) return
  activeNote.value = { ...note, content: value }
  scheduleSave(note.id, { content: value })
}

// ---- 生命周期 ----
// 页面被隐藏（切标签页 / 最小化）时立即冲刷，兜住「防抖还没到点就切走」
const handleVisibilityChange = () => {
  if (document.visibilityState === 'hidden') {
    flushSave()
  }
}

onMounted(async () => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  await loadNotes(true)
  // 侧边栏没有分页控件，这里把列表补齐（与学习室 / 面试间的做法一致）
  while (hasMoreNotes.value && notes.value.length < 500) {
    await loadNotes(false)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  flushSave()
})
</script>

<template>
  <div class="notebook-room">
    <AppHeader :tabs="tabs" :active-tab="activeTab" @tab-click="handleTabClick" />
    <div class="notebook-room__content">
      <SideBar
        :sessions="notes"
        :active-session-id="activeNoteId ?? ''"
        create-label="新建笔记"
        section-title="历史笔记"
        @create-session="createNewNote"
        @session-click="openNote(Number($event))"
        @edit-session="editNoteTitle"
        @remove-session="removeNote"
      />
      <NotebookEditor
        :title="activeNote?.title ?? ''"
        :content="activeNote?.content ?? EMPTY_NOTE_CONTENT"
        :status-text="saveStatusText"
        @update-title="handleTitleChange"
        @update-content="handleContentChange"
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
