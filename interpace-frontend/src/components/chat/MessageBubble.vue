<script setup lang="ts">
import { computed } from 'vue'
import { ChatDotRound, UserFilled } from '@element-plus/icons-vue'
import MsgFile from './MsgFile.vue'
import QuizCard from '@/components/quiz/QuizCard.vue'
import ProfileProposalCard from '@/components/profile/ProfileProposalCard.vue'
import ResumeDownloadButton from '@/components/resume/ResumeDownloadButton.vue'
import TypingIndicator from './TypingIndicator.vue'
import { DEFAULT_CHAT_MODE, RESUME_MODE, findChatMode } from '@/constants/chat-modes'
import { renderMarkdownCached } from '@/utils/markdownUtil'
import type { ProfileProposalItem } from '@/types/profile'
import type { UiMessage } from '@/types/chat'

const props = defineProps<{
    message: UiMessage
    /** message_id -> paper_id 映射；命中时在这条消息下渲染答题卡片 */
    quizPapers?: Record<number, number>
    /** message_id -> 画像待确认记录；命中时渲染画像确认卡片（T6.2） */
    profileProposals?: Record<number, ProfileProposalItem>
}>()

const emit = defineEmits<{
    openInterview: [interviewId: number]
    saveToNote: [messageId: number]
    explainTopics: [topics: string[]]
    profileUpdated: [proposal: ProfileProposalItem]
}>()

// 题库卡片：靠「入口消息 ID → 卷子 ID」映射判定，
// 历史回显与刚出题完（流式结束）两条路径用的是同一份映射。
const quizPaperId = computed(() => {
    const messageId = props.message.messageId
    if (messageId === undefined || props.message.role !== 'assistant') return undefined
    return props.quizPapers?.[messageId]
})

// 画像确认卡片：同一条消息可能同时是「简历优化结果」，判定方式与题库一致。
const profileProposal = computed(() => {
    const messageId = props.message.messageId
    if (messageId === undefined || props.message.role !== 'assistant') return undefined
    return props.profileProposals?.[messageId]
})

// 「下载 Word」：只对简历优化模式、已经落库、且答复里有内容的助手消息展示。
const canExportResume = computed(
    () =>
        props.message.role === 'assistant' &&
        !props.message.pending &&
        props.message.messageId !== undefined &&
        props.message.selectModel === RESUME_MODE &&
        props.message.text.trim().length > 0
)

const markdownHtml = computed(() => {
    if (props.message.role !== 'assistant') return ''
    // cacheKey 用 message.id，避免旧消息重复解析
    return renderMarkdownCached(props.message.text, props.message.id)
})

// 模式标签：只在助手侧、且不是默认模式时展示，避免每条消息都顶着「快速回答」。
const modeLabel = computed(() => {
    if (props.message.role !== 'assistant') return ''
    const value = props.message.selectModel
    if (value === undefined || value === DEFAULT_CHAT_MODE) return ''
    return findChatMode(value)?.label ?? ''
})

// 「存入笔记」：只对已经落库（拿得到 messageId）、并且已有内容的助手回答展示
const canSaveToNote = computed(
    () =>
        props.message.role === 'assistant' &&
        !props.message.pending &&
        props.message.messageId !== undefined &&
        props.message.text.trim().length > 0 &&
        // 题库入口消息的正文是原始 JSON，由答题卡片自带的「存入笔记」负责
        !quizPaperId.value
)

const handleSaveToNote = () => {
    const messageId = props.message.messageId
    if (messageId === undefined) return
    emit('saveToNote', messageId)
}
</script>

<template>
    <div class="message-row" :class="`message-row--${message.role}`">
        <!-- 头像 -->
        <div class="avatar" :class="`avatar--${message.role}`">
            <el-icon>
                <ChatDotRound v-if="message.role === 'assistant'" />
                <UserFilled v-else />
            </el-icon>
        </div>
        <div class="message-main">
            <!-- 消息气泡 -->
            <div class="bubble" :class="`bubble--${message.role}`">
                <!-- AI 回复：等待首个片段时展示加载动画，收到内容后切换为 Markdown 渲染 -->
                <template v-if="message.role === 'assistant'">
                    <TypingIndicator v-if="message.pending && !message.text" />
                    <!-- 出题消息的正文是约定的 JSON，交给答题卡片呈现，不直接铺原文 -->
                    <div v-else-if="!quizPaperId" class="markdown-body" v-html="markdownHtml" />
                </template>
                <!-- 用户提问：纯文本显示 -->
                <p v-else class="text">{{ message.text }}</p>
                <!-- 附件渲染 -->
                <MsgFile
                    v-for="(segment, idx) in message.segments"
                    :key="`${message.id}-${idx}`"
                    :segment="segment" />
                <!-- 面试记录卡片入口 -->
                <button
                    v-if="
                        message.status === 1 && message.interviewId && message.role === 'assistant'
                    "
                    type="button"
                    class="interview-card"
                    @click="emit('openInterview', message.interviewId)">
                    查看面试记录详情
                </button>
                <!-- 刷题评测：出题完成后在原消息下渲染答题卡片 -->
                <QuizCard
                    v-if="quizPaperId"
                    :paper-id="quizPaperId"
                    @explain-topics="emit('explainTopics', $event)" />
                <!-- 简历优化结果：导出为 Word（T6.4 / T6.5） -->
                <ResumeDownloadButton
                    v-if="canExportResume && message.messageId !== undefined"
                    :message-id="message.messageId" />
                <!-- 简历里抽出的画像信息：确认后才写入（T6.2） -->
                <ProfileProposalCard
                    v-if="profileProposal"
                    :proposal="profileProposal"
                    @updated="emit('profileUpdated', $event)" />
                <!-- 一键存入笔记：学习室与面试间共用 -->
                <button
                    v-if="canSaveToNote"
                    type="button"
                    class="note-card"
                    @click="handleSaveToNote">
                    存入笔记
                </button>
            </div>
            <!-- 模式标签 + 时间戳 -->
            <p class="meta">
                <span v-if="modeLabel" class="mode-tag">{{ modeLabel }}</span>
                <span class="time">
                    {{
                        new Date(message.createdAt * 1000).toLocaleTimeString('zh-CN', {
                            hour12: false,
                        })
                    }}
                </span>
            </p>
        </div>
    </div>
</template>

<!-- scoped: 仅作用于本组件的基础样式 -->
<style scoped lang="scss">
.message-row {
    display: flex;
    gap: 14px;
    margin-bottom: 20px;
    width: min(760px, 100%);
}

.avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
}

.avatar--assistant {
    background-color: #4385f1;
}

.avatar--user {
    background-color: #6b778a;
}

.message-main {
    width: calc(100% - 50px);
    max-width: 710px;
}

.bubble {
    border-radius: 14px;
    font-size: 18px;
    line-height: 1.7;
    padding: 14px 18px;
    border: 1px solid transparent;
    color: #2f3642;
}

.text {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
}

.bubble--assistant {
    background: #f2f1ed;
    border-color: #d8dce4;
}

.bubble--user {
    background: #d8dde8;
}

.meta {
    margin: 7px 0 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

.mode-tag {
    border: 1px solid #e6d9ae;
    border-radius: 999px;
    background: #fffaf0;
    color: #8a6d00;
    font-size: 12px;
    line-height: 1;
    padding: 3px 9px;
}

.time {
    color: #9ea6b4;
    font-size: 13px;
}

.interview-card {
    margin-top: 10px;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    background: #f7f9fc;
    color: #2f4660;
    padding: 8px 12px;
    cursor: pointer;
}

.note-card {
    margin-top: 10px;
    margin-left: 8px;
    border: 1px solid #e6d9ae;
    border-radius: 8px;
    background: #fffaf0;
    color: #8a6d00;
    padding: 8px 12px;
    cursor: pointer;
}
</style>

<!-- non-scoped: Markdown 渲染内容的全局美化样式 -->
<style>
.markdown-body {
    line-height: 1.7;
    word-break: break-word;
}

.markdown-body p {
    margin: 0 0 10px;
}

.markdown-body p:last-child {
    margin-bottom: 0;
}

.markdown-body strong {
    font-weight: 600;
}

.markdown-body em {
    font-style: italic;
}

.markdown-body a {
    color: #4385f1;
    text-decoration: none;
}

.markdown-body a:hover {
    text-decoration: underline;
}

.markdown-body ul,
.markdown-body ol {
    padding-left: 22px;
    margin: 6px 0;
}

.markdown-body li {
    margin-bottom: 4px;
}

.markdown-body blockquote {
    margin: 10px 0;
    padding: 8px 16px;
    border-left: 4px solid #4385f1;
    background: rgba(67, 133, 241, 0.06);
    border-radius: 0 6px 6px 0;
    color: #555;
}

.markdown-body blockquote p {
    margin: 0;
}

/* 行内代码 */
.markdown-body code {
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 0.88em;
    padding: 2px 6px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 4px;
    color: #d63384;
}

/* 代码块 */
.markdown-body pre.code-block {
    position: relative;
    margin: 12px 0;
    padding: 16px 18px;
    background: #1e1e2e; /* 深色背景 */
    border-radius: 8px;
    overflow-x: auto;
    font-size: 14px;
    line-height: 1.5;
}

/* 代码块右上角语言标识 */
.markdown-body pre.code-block::before {
    content: attr(data-lang);
    position: absolute;
    top: 6px;
    right: 12px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.4);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.markdown-body pre.code-block code {
    background: none;
    padding: 0;
    color: #cdd6f4; /* 适配深色背景的文本颜色 */
    font-size: inherit;
}

/* 表格 */
.markdown-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    overflow-x: auto; /* 支持横向滚动 */
    display: block;
}

.markdown-body table thead {
    background: #e8ecf4;
}

.markdown-body table th,
.markdown-body table td {
    padding: 8px 14px;
    border: 1px solid #d0d5dd;
    text-align: left;
    white-space: nowrap;
}

.markdown-body table tbody tr:nth-child(even) {
    background: #f6f8fc; /* 斑马纹 */
}

.markdown-body table tbody tr:hover {
    background: #e3edfa; /* 悬浮高亮 */
}

/* 标题 */
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
    margin: 16px 0 8px;
    line-height: 1.4;
    font-weight: 600;
}

.markdown-body h1 {
    font-size: 1.5em;
}
.markdown-body h2 {
    font-size: 1.3em;
}
.markdown-body h3 {
    font-size: 1.15em;
}
.markdown-body h4 {
    font-size: 1.05em;
}

.markdown-body hr {
    border: none;
    border-top: 1px solid #d0d5dd;
    margin: 16px 0;
}

.markdown-body img {
    max-width: 100%;
    border-radius: 6px;
}

.markdown-body input[type='checkbox'] {
    margin-right: 6px;
}
</style>
