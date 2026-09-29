<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
    createSession,
    deleteSession,
    getInterviewDetail,
    getSessionMessages,
    getSessions,
    updateSessionTitle,
} from '@/api/chat'
import ChatWindow from '@/components/chat/ChatWindow.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import SideBar from '@/components/layout/SideBar.vue'
import { useSessionStreamSender } from '@/composables/useSessionStreamSender'
import { tabs } from '@/composables/useRoomShell'
import type { InterviewDetail, SessionItem, SessionRecord, UiMessage } from '@/types/chat'

const SESSION_MODEL: 1 = 1

const route = useRoute()
const router = useRouter()

// 顶部导航与会话列表状态。
const activeTab = ref('interview-room')
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<number | null>(null)
const loadingSessions = ref(false)

// 会话分页状态（左侧侧边栏）。
const sessionPage = ref(1)
const sessionPageSize = 20
const sessionHasMore = ref(false)

// 消息分页状态（右侧聊天窗口）。
const messagePage = ref(1)
const messagePageSize = 20
const messageHasMore = ref(true)
const messageLoading = ref(false)
const messageLoadingMore = ref(false)

// 当前会话的消息列表（不做多会话缓存，保持实现更简洁）。
const uiMessages = ref<UiMessage[]>([])

// 面试详情弹窗状态。
const interviewDialogVisible = ref(false)
const interviewDetail = ref<InterviewDetail | null>(null)
const interviewLoading = ref(false)

// 统一使用秒级时间戳，和后端 created_at 语义对齐。
const nowTs = () => Math.floor(Date.now() / 1000)

watch(
    () => route.path,
    (path) => {
        const tab = tabs.find((item) => item.path === path)
        if (tab) {
            activeTab.value = tab.key
        }
    },
    { immediate: true },
)

const handleTabClick = async (tabKey: string) => {
    const selectedTab = tabs.find((tab) => tab.key === tabKey)
    if (!selectedTab) {
        return
    }
    activeTab.value = tabKey
    await router.push(selectedTab.path)
}

// 后端一条记录包含“问+答”，前端拆成两条消息气泡。
const mapRecordsToUiMessages = (records: SessionRecord[]): UiMessage[] => {
    const sorted = [...records].sort((a, b) => a.created_at - b.created_at)
    return sorted.flatMap((item) => {
        const userMessage: UiMessage = {
            id: `${item.id}-req`,
            role: 'user',
            text: item.request_text || '',
            createdAt: item.created_at,
            segments: item.request_segments || [],
        }
        const assistantMessage: UiMessage = {
            id: `${item.id}-resp`,
            role: 'assistant',
            text: item.response_text || '',
            createdAt: item.created_at,
            segments: item.response_segments || [],
            status: item.status,
            interviewId: item.interview_id,
        }
        return [userMessage, assistantMessage]
    })
}

// 拉取会话列表；reset=true 时执行首屏/刷新场景。
const loadSessions = async (reset = false) => {
    if (loadingSessions.value) return
    loadingSessions.value = true
    try {
        if (reset) {
            sessionPage.value = 1
            sessions.value = []
        }
        const data = await getSessions({
            page: sessionPage.value,
            page_size: sessionPageSize,
            session_model: SESSION_MODEL,
        })
        sessions.value = reset ? data.sessions : [...sessions.value, ...data.sessions]
        sessionHasMore.value = data.has_more
        sessionPage.value += 1
        const firstSession = sessions.value[0]
        if (!activeSessionId.value && firstSession) {
            activeSessionId.value = firstSession.id
            // 首次进入页面默认加载首个会话消息。
            await loadMessages(true)
        }
    } finally {
        loadingSessions.value = false
    }
}

// 点击侧边栏会话：切换前先停止旧流，避免串写到新会话。
const handleSessionClick = async (id: number | string) => {
    const nextId = Number(id)
    if (Number.isNaN(nextId) || nextId === activeSessionId.value) {
        return
    }
    // 切换会话前先停掉旧流，防止旧回调写到新会话界面。
    stopActiveStream()
    activeSessionId.value = nextId
    await loadMessages(true)
}

// 拉取消息列表；支持首屏重置与上拉分页。
const loadMessages = async (reset = false) => {
    if (!activeSessionId.value) return
    if (messageLoading.value || messageLoadingMore.value) return

    if (reset) {
        // 切换会话或首次进入时重置分页状态。
        messageLoading.value = true
        messagePage.value = 1
        messageHasMore.value = true
        uiMessages.value = []
    } else {
        if (!messageHasMore.value) return
        // 上拉加载更多时使用独立 loading，避免和首屏 loading 混淆。
        messageLoadingMore.value = true
    }

    try {
        const data = await getSessionMessages(activeSessionId.value, {
            page: messagePage.value,
            page_size: messagePageSize,
            session_model: SESSION_MODEL,
        })
        const next = mapRecordsToUiMessages(data.messages)
        uiMessages.value = [...uiMessages.value, ...next]
        messageHasMore.value = data.has_more
        messagePage.value += 1
    } finally {
        messageLoading.value = false
        messageLoadingMore.value = false
    }
}

// 新建会话：创建成功后自动切换到新会话并拉取消息。
const createNewSession = async () => {
    try {
        const promptResult = (await ElMessageBox.prompt('请输入会话主题标题', '新建会话', {
            inputValue: '新会话',
            inputPattern: /.+/,
            inputErrorMessage: '标题不能为空',
        })) as { value: string }
        const result = await createSession({ title: promptResult.value.trim(), session_model: 1 })
        sessions.value.unshift(result.session)
        stopActiveStream()
        activeSessionId.value = result.session.id
        await loadMessages(true)
    } catch {
        // 用户取消输入时不提示。
    }
}

// 编辑会话标题：后端更新成功后回写本地 sessions。
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
        if (index >= 0) {
            sessions.value[index] = result.session
        }
        ElMessage.success('会话标题已更新')
    } catch {
        // 用户取消输入时不提示。
    }
}

// 删除会话：若删除的是当前会话，自动切到下一条并重载消息。
const removeSession = async (id: number | string) => {
    const sessionId = Number(id)
    const target = sessions.value.find((item) => item.id === sessionId)
    if (!target) return
    try {
        await ElMessageBox.confirm(`确认删除会话「${target.title}」吗？`, '删除会话', {
            type: 'warning',
            confirmButtonText: '删除',
            cancelButtonText: '取消',
        })
        await deleteSession(sessionId, SESSION_MODEL)
        sessions.value = sessions.value.filter((item) => item.id !== sessionId)
        if (activeSessionId.value === sessionId) {
            stopActiveStream()
            const next = sessions.value[0]
            activeSessionId.value = next ? next.id : null
            if (activeSessionId.value) {
                // 删除当前会话后自动切换到新的首会话并加载消息。
                await loadMessages(true)
            } else {
                uiMessages.value = []
                messageHasMore.value = false
            }
        }
        ElMessage.success('会话已删除')
    } catch {
        // 用户取消删除时不提示。
    }
}

// 打开面试详情弹窗：按需请求，避免首屏冗余数据。
const openInterviewDetail = async (interviewId: number) => {
    // 面试卡片点击后再按需请求详情，减少首屏请求体积。
    interviewLoading.value = true
    try {
        interviewDetail.value = await getInterviewDetail(interviewId)
        interviewDialogVisible.value = true
    } finally {
        interviewLoading.value = false
    }
}

// 附件入口占位：当前版本仅提示，后续可接上传流程。
const handleAttach = () => {
    ElMessage.info('当前版本暂未接入附件上传')
}

// 统一封装流式发送：负责占位消息、增量更新、结束后同步。
const { sending, stopActiveStream, send } = useSessionStreamSender({
    sessionModel: SESSION_MODEL,
    getActiveSessionId: () => activeSessionId.value,
    // 创建本地占位消息：用户消息 + 助手空消息（后续不断 append delta）。
    createPending: (text, sessionId) => {
        const baseId = `${sessionId}-${Date.now()}`
        const userMessage: UiMessage = {
            id: `${baseId}-user`,
            role: 'user',
            text,
            createdAt: nowTs(),
            segments: [],
        }
        const assistantMessage = reactive<UiMessage>({
            id: `${baseId}-assistant`,
            role: 'assistant',
            text: '',
            createdAt: nowTs(),
            segments: [],
            // 首个片段到达前展示加载动画
            pending: true,
        })
        // 只会追加到当前会话消息列表；后续 delta 只更新最后一条 assistant。
        uiMessages.value = [...uiMessages.value, userMessage, assistantMessage]
        return {
            // SSE delta 到达时追加文本，形成“打字机”效果。
            appendDelta: (delta) => {
                assistantMessage.pending = false
                assistantMessage.text += delta
            },
            // done 事件到达时用全文兜底覆盖，避免丢字/重字。
            finish: (fullText) => {
                assistantMessage.pending = false
                assistantMessage.text = fullText || assistantMessage.text
            },
            // 出错或被打断时结束等待状态，避免加载动画一直转。
            cancel: () => {
                assistantMessage.pending = false
            },
        }
    },
    // 流结束后不做自动回刷，避免再次请求消息列表导致页面“刷新/跳动”。
    onError: (message) => ElMessage.error(message),
})

// 发送入口：复用通用流式发送 composable。
const handleSend = async (text: string) => {
    await send(text)
}

// 页面初始化：先拉第一页，再尽量补齐会话列表（最多 500 条）。
onMounted(async () => {
    await loadSessions(true)
    while (sessionHasMore.value && sessions.value.length < 500) {
        await loadSessions(false)
    }
})

// 页面卸载时中断流，避免后台继续推送与状态泄漏。
onBeforeUnmount(() => {
    stopActiveStream()
})
</script>

<template>
    <div class="interview-room">
        <AppHeader :tabs="tabs" :active-tab="activeTab" @tab-click="handleTabClick" />
        <div class="interview-room__content">
            <SideBar
                :sessions="sessions"
                :active-session-id="activeSessionId ?? ''"
                @create-session="createNewSession"
                @session-click="handleSessionClick"
                @edit-session="editSessionTitle"
                @remove-session="removeSession" />
            <ChatWindow
                :messages="uiMessages"
                :has-more="messageHasMore"
                :loading-more="messageLoadingMore || messageLoading"
                :disabled="sending || !activeSessionId"
                @load-more="loadMessages(false)"
                @open-interview="openInterviewDetail"
                @send="handleSend"
                @attach="handleAttach" />
        </div>
    </div>

    <el-dialog v-model="interviewDialogVisible" title="面试记录详情" width="720px">
        <template v-if="interviewLoading">
            <p>正在加载面试记录...</p>
        </template>
        <template v-else-if="interviewDetail">
            <div class="qa-list">
                <div v-for="(qa, idx) in interviewDetail.qa_object" :key="idx" class="qa-item">
                    <p class="q">
                        <strong>Q{{ idx + 1 }}：</strong>{{ qa.question }}
                    </p>
                    <p class="a">
                        <strong>A{{ idx + 1 }}：</strong>{{ qa.answer }}
                    </p>
                </div>
            </div>
        </template>
    </el-dialog>
</template>

<style scoped lang="scss">
.interview-room {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.interview-room__content {
    flex: 1;
    min-height: 0;
    display: flex;
}

.qa-list {
    max-height: 480px;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.qa-item {
    border: 1px solid #e1e5ee;
    border-radius: 8px;
    padding: 10px 12px;
    background: #f9fbff;
}

.q,
.a {
    margin: 0;
    line-height: 1.6;
    white-space: pre-wrap;
}

.a {
    margin-top: 8px;
}
</style>
