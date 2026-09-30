<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
    createSession,
    deleteSession,
    finishInterview,
    getInterviewDetail,
    getSessionMessages,
    getSessions,
    updateSessionTitle,
} from '@/api/chat'
import ChatWindow from '@/components/chat/ChatWindow.vue'
import VoiceInterviewPanel from '@/components/speech/VoiceInterviewPanel.vue'
import EvaluationPanel from '@/components/evaluation/EvaluationPanel.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import SideBar from '@/components/layout/SideBar.vue'
import { useSessionStreamSender } from '@/composables/useSessionStreamSender'
import { useRuntimeConfig } from '@/composables/useRuntimeConfig'
import { tabs } from '@/constants/nav-tabs'
import { importNoteFromMessage } from '@/api/note'
import { getProfileProposalsBySession } from '@/api/profile'
import {
    DEFAULT_CHAT_MODE,
    EVALUATION_MODE,
    INTERVIEW_MODES,
    INTERVIEW_MODE,
    KNOWLEDGE_MODE,
} from '@/constants/chat-modes'
import { useVoiceInterview } from '@/composables/useVoiceInterview'
import type { ProfileProposalItem } from '@/types/profile'
import type {
    InterviewDetail,
    MessageSegment,
    SessionItem,
    SessionRecord,
    UiMessage,
} from '@/types/chat'

const SESSION_MODEL: 1 = 1

const route = useRoute()
const router = useRouter()

// 顶部导航与会话列表状态。
const activeTab = ref('interview-room')
const sessions = ref<SessionItem[]>([])
const activeSessionId = ref<number | null>(null)
const loadingSessions = ref(false)
// 当前选中的模式（select_model），每次发送时一并提交给后端。
const selectedMode = ref<number>(DEFAULT_CHAT_MODE)

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

// message_id -> 画像待确认记录：命中时在该消息下渲染画像确认卡片（T6.2）。
// 与题库卡片一样，历史回显和刚抽完两条路径共用这一份映射。
const profileProposals = ref<Record<number, ProfileProposalItem>>({})

// 语音面试（T7.7）：只在「模拟面试」模式下显示面板，切走模式时自动断开连接。
// 这里解构出来用：模板对嵌套在普通对象里的 ref 不会自动解包，
// 拉平成顶层绑定后模板里就能直接当值用（`playback` 本身是 reactive，保持原样）。
const {
    status: voiceStatus,
    connected: voiceConnected,
    asrPartial: voiceAsrPartial,
    asrFinal: voiceAsrFinal,
    replyText: voiceReplyText,
    timeoutMessage: voiceTimeoutMessage,
    micLevels: voiceMicLevels,
    playback: voicePlayback,
    connect: voiceConnect,
    startRecording: voiceStartRecording,
    stopRecording: voiceStopRecording,
    sendText: voiceSendText,
    disconnect: voiceDisconnect,
} = useVoiceInterview()
const voiceEnabled = ref(false)
const showVoicePanel = computed(() => selectedMode.value === INTERVIEW_MODE && voiceEnabled.value)

// 语音面试的可用性由后端配置决定（T12.4）：演示环境会在配置里整体关掉它。
// 拉取失败按"可用"处理，真正的拦截在后端 WebSocket 路由上。
const { runtimeConfig: runtimeConfigState, ensureRuntimeConfig } = useRuntimeConfig()
const voiceInterviewAvailable = computed(
    () => runtimeConfigState.value?.features.voice_interview ?? true
)
const showVoiceToggle = computed(
    () => selectedMode.value === INTERVIEW_MODE && voiceInterviewAvailable.value
)

// 演示环境的单场面试时长到点（T12.4）：服务端已把这场面试结束掉，
// 这里只负责告知用户，并刷新一次消息列表——入口消息卡片上的 interviewId 会让
// 「结束面试 / 查看复盘」的入口亮起来，用户可以接着看复盘。
watch(voiceTimeoutMessage, async (message) => {
    if (!message) return
    ElMessage.warning(message)
    await loadMessages(true)
})

// 面试复盘（T8.5）：切到「面试复盘」模式时，把这场会话里最近的面试记录交给面板。
// 一场面试的入口消息带 interviewId，直接取最后一条即可。
const latestInterviewId = computed<number | null>(() => {
    for (let index = uiMessages.value.length - 1; index >= 0; index -= 1) {
        const id = uiMessages.value[index].interviewId
        if (typeof id === 'number') {
            return id
        }
    }
    return null
})
const showEvaluationPanel = computed(() => selectedMode.value === EVALUATION_MODE)

// 「结束面试」（T7.8）：结束 → 自动切到面试复盘 → 立刻生成一份复盘
const finishing = ref(false)
const evaluationPanelRef = ref<InstanceType<typeof EvaluationPanel> | null>(null)
const showFinishButton = computed(
    () => selectedMode.value === INTERVIEW_MODE && latestInterviewId.value !== null,
)

const handleFinishInterview = async () => {
    const interviewId = latestInterviewId.value
    if (!interviewId || finishing.value) return
    finishing.value = true
    try {
        const result = await finishInterview(interviewId)
        ElMessage.success(
            result.already_finished
                ? '这场面试之前已经结束了，直接看复盘'
                : `面试已结束（${result.interview_duration} 秒 / ${result.qa_count} 轮问答），正在生成复盘…`,
        )
        // 切到复盘模式：面板挂载后会自己去读一次，这里再主动触发一次生成
        selectedMode.value = EVALUATION_MODE
        await nextTick()
        await evaluationPanelRef.value?.generate()
    } finally {
        finishing.value = false
    }
}

// 复盘结果里的「针对薄弱点讲一讲」：切到知识精讲继续问，复用已有的流式链路
const handleExplainTopics = async (topics: string[]) => {
    if (!topics.length) return
    selectedMode.value = KNOWLEDGE_MODE
    await handleSend(`请讲讲这几个薄弱知识点：${topics.join('、')}`, [])
}

const toggleVoiceInterview = async () => {
    if (voiceEnabled.value) {
        voiceDisconnect()
        voiceEnabled.value = false
        return
    }
    if (!activeSessionId.value) {
        ElMessage.warning('请先创建或选择一个会话')
        return
    }
    voiceEnabled.value = true
    await voiceConnect(activeSessionId.value, SESSION_MODEL)
}

// 切走「模拟面试」模式时收掉语音通道：避免麦克风与连接在后台一直开着。
watch(selectedMode, (mode) => {
    if (mode !== INTERVIEW_MODE && voiceEnabled.value) {
        voiceDisconnect()
        voiceEnabled.value = false
    }
})

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

// 拉取当前会话的画像待确认记录：只更新 profileProposals，不碰消息列表，
// 所以刷新它不会引起消息区跳动。
const loadProfileProposals = async () => {
    const sessionId = activeSessionId.value
    if (!sessionId) {
        profileProposals.value = {}
        return
    }
    try {
        const data = await getProfileProposalsBySession(sessionId)
        // 请求期间可能已经切了会话，回来时确认仍是同一个再写入。
        if (activeSessionId.value !== sessionId) return
        const map: Record<number, ProfileProposalItem> = {}
        for (const item of data.items) map[item.message_id] = item
        profileProposals.value = map
    } catch {
        // 画像拉取失败不影响聊天主链路，静默处理
    }
}

// 会话切换（含首屏选中）时同步刷新画像映射。
watch(activeSessionId, () => {
    void loadProfileProposals()
})

// 确认或忽略后：就地替换这一条，避免整页重拉。
const handleProfileUpdated = (proposal: ProfileProposalItem) => {
    profileProposals.value = {
        ...profileProposals.value,
        [proposal.message_id]: proposal
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

// 统一封装流式发送：负责占位消息、增量更新、结束后同步。
const { sending, stopActiveStream, send } = useSessionStreamSender({
    sessionModel: SESSION_MODEL,
    getActiveSessionId: () => activeSessionId.value,
    // 创建本地占位消息：用户消息 + 助手空消息（后续不断 append delta）。
    createPending: (text, sessionId, segments) => {
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
            segments: [],
            // 首个片段到达前展示加载动画
            pending: true,
            // 与请求时提交的模式保持一致，否则要刷新页面才看得到模式标签
            selectModel: selectedMode.value,
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
            // 收到 start 事件后补上真实消息 ID，「存入笔记」要用
            setMessageId: (messageId: number) => {
                assistantMessage.messageId = messageId
            },
            // 本轮开了面试：把入口标记补上，让「查看面试记录详情」卡片当场出现，
            // 不用等刷新（后端此时已把消息 status 置为 1）。
            setResult: ({ interviewId }) => {
                if (interviewId === null) return
                assistantMessage.interviewId = interviewId
                assistantMessage.status = 1
            },
        }
    },
    // 流结束后不做自动回刷，避免再次请求消息列表导致页面“刷新/跳动”。
    onError: (message) => ElMessage.error(message),
})

// 发送入口：复用通用流式发送 composable。
const handleSend = async (text: string, segments: MessageSegment[]) => {
    await send(text, selectedMode.value, segments)
    // 简历优化这一轮可能抽出画像：流结束后刷一次映射，让确认卡片马上出现。
    await loadProfileProposals()
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

// 页面初始化：先拉第一页，再尽量补齐会话列表（最多 500 条）。
onMounted(async () => {
    // 运行时能力开关：决定「语音面试」按钮显不显示，尽早拉一次（演示环境会关掉它）。
    void ensureRuntimeConfig()
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
            <div class="interview-room__main">
                <!-- 面试复盘（T8.5）：只在「面试复盘」模式下显示 -->
                <EvaluationPanel
                    v-if="showEvaluationPanel"
                    ref="evaluationPanelRef"
                    :interview-id="latestInterviewId"
                    @explain-topics="handleExplainTopics" />
                <VoiceInterviewPanel
                    v-if="showVoicePanel"
                    :status="voiceStatus"
                    :connected="voiceConnected"
                    :asr-partial="voiceAsrPartial"
                    :asr-final="voiceAsrFinal"
                    :reply-text="voiceReplyText"
                    :mic-levels="voiceMicLevels"
                    :playback="voicePlayback"
                    @start="voiceStartRecording"
                    @stop="voiceStopRecording"
                    @send-text="voiceSendText" />
                <ChatWindow
                    :messages="uiMessages"
                    v-model:mode="selectedMode"
                    :modes="INTERVIEW_MODES"
                    :has-more="messageHasMore"
                    :profile-proposals="profileProposals"
                    :show-voice-toggle="showVoiceToggle"
                    :voice-enabled="voiceEnabled"
                    :show-finish-button="showFinishButton"
                    :finishing="finishing"
                    :loading-more="messageLoadingMore || messageLoading"
                    :disabled="sending || !activeSessionId"
                    :no-session="!loadingSessions && !activeSessionId"
                    :sending="sending"
                    @create-session="createNewSession"
                    @load-more="loadMessages(false)"
                    @open-interview="openInterviewDetail"
                    @send="handleSend"
                    @save-to-note="handleSaveToNote"
                    @profile-updated="handleProfileUpdated"
                    @toggle-voice="toggleVoiceInterview"
                    @finish-interview="handleFinishInterview"
                    @stop="stopActiveStream" />
            </div>
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
    /* 房间自身不滚动：内容超出时裁掉，而不是把整页顶出滚动条 */
    overflow: hidden;
}

.interview-room__content {
    flex: 1;
    min-height: 0;
    display: flex;
    overflow: hidden;
}

.interview-room__main {
    flex: 1;
    min-width: 0;
    /* min-height + overflow 缺一不可：前者让这一列能被压缩，
       后者保证内容溢不出去。缺了就会「整页变长、输入框跟着页面滚」。 */
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
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
