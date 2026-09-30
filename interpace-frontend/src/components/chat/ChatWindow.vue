<script setup lang="ts">
import { computed } from 'vue'
import ChatInput from './ChatInput.vue'
import MessageList from './MessageList.vue'
import type { ChatMode } from '@/constants/chat-modes'
import type { ProfileProposalItem } from '@/types/profile'
import type { MessageSegment, UiMessage } from '@/types/chat'

const props = defineProps<{
  messages: UiMessage[]
  /** 当前房间可选的模式列表 */
  modes: ChatMode[]
  /** 当前选中的 select_model */
  mode: number
  hasMore?: boolean
  loadingMore?: boolean
  disabled?: boolean
  /** 是否正在生成回答：透传给 ChatInput 决定显示发送还是停止 */
  sending?: boolean
  /** message_id -> paper_id 映射，透传到消息气泡用于渲染答题卡片 */
  quizPapers?: Record<number, number>
  /** message_id -> 画像待确认记录，透传到消息气泡用于渲染确认卡片 */
  profileProposals?: Record<number, ProfileProposalItem>
  /** 是否显示输入框底部的「语音面试」按钮（只有面试间打开） */
  showVoiceToggle?: boolean
  /** 语音面试是否已开启 */
  voiceEnabled?: boolean
  /** 是否显示「结束面试」按钮（T7.8） */
  showFinishButton?: boolean
  /** 结束面试请求进行中 */
  finishing?: boolean
  /**
   * 当前房间**一个会话都没有**（且会话列表已经加载完）。
   *
   * 有别于"有会话但还没消息"：那种情况用户点进去就能直接问。
   * 这里为真时输入框是禁用的（消息必须挂在某个会话上），
   * 所以要在消息区给出明确出口，否则用户只会觉得"输入框坏了"。
   */
  noSession?: boolean
}>()

const emit = defineEmits<{
  send: [text: string, segments: MessageSegment[]]
  stop: []
  loadMore: []
  openInterview: [interviewId: number]
  saveToNote: [messageId: number]
  explainTopics: [topics: string[]]
  profileUpdated: [proposal: ProfileProposalItem]
  toggleVoice: []
  finishInterview: []
  /** 空状态里点「新建会话」 */
  createSession: []
  'update:mode': [value: number]
}>()

// 没有会话时输入框是禁用的，占位文案要说明原因，而不是继续写"输入你的回答…"。
const inputPlaceholder = computed(() =>
  props.noSession ? '先新建会话，再开始提问' : '输入你的回答...'
)
</script>

<template>
  <main class="chat-window">
    <!-- 一个会话都没有时的引导。放在消息区而不是弹提示：
         它是一个"需要用户做点什么"的稳定状态，不是一次性通知。 -->
    <div v-if="noSession" class="chat-empty">
      <p class="chat-empty__title">还没有会话</p>
      <p class="chat-empty__body">消息需要挂在某个会话下，先建一个，然后就能开始提问。</p>
      <el-button class="chat-empty__action" type="primary" @click="emit('createSession')">
        新建会话
      </el-button>
      <p class="chat-empty__hint">也可以在左侧边栏点「新建会话」。</p>
    </div>
    <MessageList
      v-else
      :messages="messages"
      :has-more="hasMore"
      :loading-more="loadingMore"
      :quiz-papers="quizPapers"
      :profile-proposals="profileProposals"
      @load-more="emit('loadMore')"
      @open-interview="emit('openInterview', $event)"
      @save-to-note="emit('saveToNote', $event)"
      @explain-topics="emit('explainTopics', $event)"
      @profile-updated="emit('profileUpdated', $event)"
    />
    <ChatInput
      :disabled="disabled"
      :placeholder="inputPlaceholder"
      :modes="modes"
      :mode="mode"
      :sending="sending"
      :show-voice-toggle="showVoiceToggle"
      :voice-enabled="voiceEnabled"
      :show-finish-button="showFinishButton"
      :finishing="finishing"
      @send="(text, segments) => emit('send', text, segments)"
      @stop="emit('stop')"
      @toggle-voice="emit('toggleVoice')"
      @finish-interview="emit('finishInterview')"
      @update:mode="emit('update:mode', $event)" />
  </main>
</template>

<style scoped lang="scss">
.chat-window {
  flex: 1;
  min-width: 0;
  /* 纵向 flex 里必须显式给 min-height:0，否则内层消息列表的「自动最小高度」
     会把它撑到内容高度，滚动条就跑到整页去了（而不是留在消息列表里）。 */
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 没有任何会话时的引导区：占据消息区、垂直居中，与输入框一起构成一个完整的起始状态。 */
.chat-empty {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  text-align: center;
}

.chat-empty__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #30353e;
}

.chat-empty__body {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #7b8290;
  max-width: 30em;
}

.chat-empty__action {
  margin-top: 8px;
  border-radius: 999px;
  padding: 0 24px;
}

.chat-empty__hint {
  margin: 0;
  font-size: 12px;
  color: #9aa1a8;
}
</style>
