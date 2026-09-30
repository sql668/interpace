<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
    createSession,
    deleteSession,
    getSessionMessages,
    getSessions,
    updateSessionTitle,
} from '@/api/chat'
import ChatWindow from '@/components/chat/ChatWindow.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import SideBar from '@/components/layout/SideBar.vue'
import { useSessionStreamSender } from '@/composables/useSessionStreamSender'
import { tabs } from '@/constants/nav-tabs'
import { importNoteFromMessage } from '@/api/note'
import { getQuizPapersBySession } from '@/api/quiz'
import { DEFAULT_CHAT_MODE, STUDY_MODES, KNOWLEDGE_MODE } from '@/constants/chat-modes'
import type { MessageSegment, SessionItem, SessionRecord, UiMessage } from '@/types/chat'

// 学习室固定会话模式 0。
const SESSION_MODEL: 0 = 0

const route = useRoute()
const router = useRouter()

// 顶部标签与会话列表状态。
const activeTab = ref('study-room')
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<number | null>(null)
const loadingSessions = ref(false)
// 当前选中的模式（select_model），每次发送时一并提交给后端。
const selectedMode = ref<number>(DEFAULT_CHAT_MODE)
// 会话分页状态（左侧）。
const sessionPage = ref(1)
const sessionPageSize = 20
const sessionHasMore = ref(false)

// 消息分页状态（右侧）。
const messagePage = ref(1)
const messagePageSize = 20
const messageHasMore = ref(true)
const messageLoading = ref(false)
const messageLoadingMore = ref(false)

// 以 sessionId 为 key 的消息缓存，支持多会话快速切换回显。
const sessionMessages = ref<Record<string, UiMessage[]>>({})

// message_id -> paper_id：命中时在对应消息下渲染答题卡片。
// 历史回显与刚出题完（流式结束）都靠这份映射，不另存一份状态。
const quizPapers = ref<Record<number, number>>({})

// 与后端时间字段保持一致：秒级时间戳。
const nowTs = () => Math.floor(Date.now() / 1000)

watch(
    () => route.path,
    (path) => {
        const tab = tabs.find((item) => item.path === path)
        if (tab) activeTab.value = tab.key
    },
    { immediate: true },
)

const handleTabClick = async (tabKey: string) => {
    const selectedTab = tabs.find((tab) => tab.key === tabKey)
    if (!selectedTab) return
    activeTab.value = tabKey
    await router.push(selectedTab.path)
}

// 当前激活会话对应的消息列表（空会话返回空数组）。
const activeMessages = computed(() => {
    const id = activeSessionId.value
    if (!id) return []
    return sessionMessages.value[String(id)] ?? []
})

// 后端一条记录包含“问+答”，前端拆成两条消息气泡。
const mapRecordsToUiMessages = (records: SessionRecord[]): UiMessage[] => {
    const sorted = [...records].sort((a, b) => a.created_at - b.created_at)
    return sorted.flatMap((item) => {
        const userMessage: UiMessage = {
            id: `${item.id}-req`,
            messageId: item.id,
            role: 'user',
            text: item.request_text || '',
            createdAt: item.created_at,
            segments: item.request_segments || [],
        }
        const assistantMessage: UiMessage = {
            id: `${item.id}-resp`,
            messageId: item.id,
            role: 'assistant',
            text: item.response_text || '',
            createdAt: item.created_at,
            segments: item.response_segments || [],
            status: item.status,
            interviewId: item.interview_id,
            selectModel: item.select_model,
        }
        return [userMessage, assistantMessage]
    })
}

// 拉取消息：reset 时重置分页并覆盖当前会话缓存，否则追加分页。
const loadMessages = async (reset = false) => {
    if (!activeSessionId.value) return
    if (messageLoading.value || messageLoadingMore.value) return

    if (reset) {
        messageLoading.value = true
        messagePage.value = 1
        messageHasMore.value = true
        sessionMessages.value[String(activeSessionId.value)] = []
    } else {
        if (!messageHasMore.value) return
        messageLoadingMore.value = true
    }

    try {
        const data = await getSessionMessages(activeSessionId.value, {
            page: messagePage.value,
            page_size: messagePageSize,
            session_model: SESSION_MODEL,
        })
        const key = String(activeSessionId.value)
        const next = mapRecordsToUiMessages(data.messages)
        sessionMessages.value[key] = [...(sessionMessages.value[key] ?? []), ...next]
        messageHasMore.value = data.has_more
        messagePage.value += 1
    } finally {
        messageLoading.value = false
        messageLoadingMore.value = false
    }
}

// 拉取当前会话的题库映射：切换会话、出题完成后都要刷新一次。
// 只更新 quizPapers，不碰消息列表，所以不会引起消息区“跳动”。
const loadQuizPapers = async () => {
    const sessionId = activeSessionId.value
    if (!sessionId) {
        quizPapers.value = {}
        return
    }
    try {
        const data = await getQuizPapersBySession(sessionId)
        // 会话可能在请求期间被切换，回来时确认仍是同一个再写入。
        if (activeSessionId.value !== sessionId) return
        const map: Record<number, number> = {}
        for (const paper of data.items) map[paper.message_id] = paper.id
        quizPapers.value = map
    } catch {
        // 题库拉取失败不影响聊天主链路，静默处理
    }
}

// 会话切换（含首屏选中）时同步刷新题库映射。
watch(activeSessionId, () => {
    void loadQuizPapers()
})

// 拉取会话列表：reset 场景用于首屏初始化或整体刷新。
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
            session_model: SESSION_MODEL,
        })
        sessions.value = reset ? data.sessions : [...sessions.value, ...data.sessions]
        sessionHasMore.value = data.has_more
        sessionPage.value += 1
        const first = sessions.value[0]
        if (!activeSessionId.value && first) {
            activeSessionId.value = first.id
            await loadMessages(true)
        }
    } finally {
        loadingSessions.value = false
    }
}

// 新建会话：创建后自动切换并进入该会话消息页。
const createNewSession = async () => {
    try {
        const promptResult = (await ElMessageBox.prompt('请输入会话主题标题', '新建会话', {
            inputValue: '学习主题',
            inputPattern: /.+/,
            inputErrorMessage: '标题不能为空',
        })) as { value: string }
        const result = await createSession({
            title: promptResult.value.trim(),
            session_model: SESSION_MODEL,
        })
        sessions.value.unshift(result.session)
        stopActiveStream()
        activeSessionId.value = result.session.id
        await loadMessages(true)
    } catch {
        // 用户取消时不提示
    }
}

// 切换会话：先停流再切换，防止旧流写入新会话消息。
const handleSessionClick = async (id: number | string) => {
    const nextId = Number(id)
    if (Number.isNaN(nextId) || nextId === activeSessionId.value) return
    stopActiveStream()
    activeSessionId.value = nextId
    await loadMessages(true)
}

// 编辑标题并回写本地会话列表，保持 UI 与后端一致。
const editSessionTitle = async (id: number | string) => {
    const sessionId = Number(id)
    const target = sessions.value.find((item) => item.id === sessionId)
    if (!target) return
    try {
        const promptResult = (await ElMessageBox.prompt('请输入新的会话标题', '编辑标题', {
            inputValue: target.title,
            inputPattern: /.+/,
            inputErrorMessage: '标题不能为空',
        })) as { value: string }
        const result = await updateSessionTitle(
            sessionId,
            { title: promptResult.value.trim() },
            SESSION_MODEL,
        )
        const index = sessions.value.findIndex((item) => item.id === sessionId)
        if (index >= 0) sessions.value[index] = result.session
        ElMessage.success('会话标题已更新')
    } catch {
        // 用户取消时不提示
    }
}

// 删除会话并清理缓存；若删的是当前会话则自动切换到下一会话。
const removeSession = async (id: number | string) => {
    const sessionId = Number(id)
    const target = sessions.value.find((item) => item.id === sessionId)
    if (!target) return
    try {
        await ElMessageBox.confirm(`确认删除会话「${target.title}」吗？`, '删除会话', {
            type: 'warning',
        })
        await deleteSession(sessionId, SESSION_MODEL)
        sessions.value = sessions.value.filter((item) => item.id !== sessionId)
        delete sessionMessages.value[String(sessionId)]
        if (activeSessionId.value === sessionId) {
            stopActiveStream()
            const next = sessions.value[0]
            activeSessionId.value = next ? next.id : null
            if (next) {
                await loadMessages(true)
            } else {
                messageHasMore.value = false
            }
        }
        ElMessage.success('会话已删除')
    } catch {
        // 用户取消时不提示
    }
}

// 通用流式发送：统一处理占位、delta 拼接、结束同步、错误提示。
const { sending, stopActiveStream, send } = useSessionStreamSender({
    sessionModel: SESSION_MODEL,
    getActiveSessionId: () => activeSessionId.value,
    // 构建一对“用户+助手”临时消息，先渲染再接收流式增量。
    createPending: (text, sessionId, segments) => {
        const key = String(sessionId)
        const list = [...(sessionMessages.value[key] ?? [])]
        const baseId = `${sessionId}-${Date.now()}`
        const userMessage: UiMessage = {
            id: `${baseId}-user`,
            role: 'user',
            text,
            createdAt: nowTs(),
            // 附件段直接来自已经上传成功的附件，气泡里会渲染出来
            segments,
        }
        const assistantMessage = reactive<UiMessage>({
            id: `${baseId}-assistant`,
            role: 'assistant',
            text: '',
            createdAt: nowTs(),
            segments: [] as MessageSegment[],
            // 首个片段到达前展示加载动画
            pending: true,
            // 与请求时提交的模式保持一致，否则要刷新页面才看得到模式标签
            selectModel: selectedMode.value,
        })
        list.push(userMessage, assistantMessage)
        sessionMessages.value[key] = list
        return {
            // 每个增量片段实时追加到助手消息。
            appendDelta: (delta) => {
                assistantMessage.pending = false
                assistantMessage.text += delta
            },
            // 流完成后使用服务端完整文本兜底。
            finish: (fullText) => {
                assistantMessage.pending = false
                assistantMessage.text = fullText || assistantMessage.text
            },
            // 出错或被打断时结束等待状态，避免加载动画一直转。
            cancel: () => {
                assistantMessage.pending = false
            },
            // 收到 start 事件后补上真实消息 ID，「存入笔记」要用
            setMessageId: (messageId: number) => {
                assistantMessage.messageId = messageId
            },
        }
    },
    // 流结束后不做自动回刷，避免再次请求消息列表导致页面“刷新/跳动”。
    onError: (message) => ElMessage.error(message),
})

// 发送入口：调用 composable 内的 send。
const handleSend = async (text: string, segments: MessageSegment[]) => {
    await send(text, selectedMode.value, segments)
    // 本轮可能是出题：流结束后刷一次题库映射，让答题卡片马上出现在这条消息下。
    await loadQuizPapers()
}

// 「针对薄弱点讲一讲」：切到知识精讲模式，把这几个知识点发出去。
const handleExplainTopics = async (topics: string[]) => {
    if (!topics.length) return
    selectedMode.value = KNOWLEDGE_MODE
    await handleSend(`请讲讲这几个薄弱知识点：${topics.join('、')}`, [])
}

// 「存入笔记」：同一时刻只处理一条，避免连点并发创建两条笔记
const importingNoteMessageId = ref<number | null>(null)

const handleSaveToNote = async (messageId: number) => {
    if (importingNoteMessageId.value !== null) return
    importingNoteMessageId.value = messageId
    try {
        const result = await importNoteFromMessage({ message_id: messageId })
        if (result.created) {
            ElMessage.success('已存入笔记')
        } else {
            ElMessage.info('这条消息之前已存入笔记')
        }
    } finally {
        importingNoteMessageId.value = null
    }
}

// 进入页面后预加载会话列表；循环拉取到上限以提升切换体验。
onMounted(async () => {
    await loadSessions(true)
    while (sessionHasMore.value && sessions.value.length < 500) {
        await loadSessions(false)
    }
})

// 退出页面时中断活动流，避免状态残留。
onBeforeUnmount(() => {
    stopActiveStream()
})
</script>

<template>
    <div class="study-room">
        <AppHeader :tabs="tabs" :active-tab="activeTab" @tab-click="handleTabClick" />
        <div class="study-room__content">
            <SideBar
                :sessions="sessions"
                :active-session-id="activeSessionId ?? ''"
                @create-session="createNewSession"
                @session-click="handleSessionClick"
                @edit-session="editSessionTitle"
                @remove-session="removeSession" />
            <ChatWindow
                :messages="activeMessages"
                v-model:mode="selectedMode"
                :modes="STUDY_MODES"
                :quiz-papers="quizPapers"
                :has-more="messageHasMore"
                :loading-more="messageLoadingMore || messageLoading"
                :disabled="sending || !activeSessionId"
                :no-session="!loadingSessions && !activeSessionId"
                :sending="sending"
                @create-session="createNewSession"
                @load-more="loadMessages(false)"
                @send="handleSend"
                @save-to-note="handleSaveToNote"
                @explain-topics="handleExplainTopics"
                @stop="stopActiveStream" />
        </div>
    </div>
</template>

<style scoped lang="scss">
.study-room {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    /* 与面试间同一条规则：房间自身不滚动，只让右侧消息列表滚 */
    overflow: hidden;
}

.study-room__content {
    flex: 1;
    min-height: 0;
    display: flex;
    overflow: hidden;
}
</style>
