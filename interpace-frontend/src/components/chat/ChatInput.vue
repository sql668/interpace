<script setup lang="ts">
import {
  CircleCheck,
  Close,
  Document,
  Microphone,
  Plus,
  Promotion,
  VideoPause
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import ModeSelector from './ModeSelector.vue'
import { ElMessage } from 'element-plus'
import { uploadFile } from '@/api/upload'
import { useRuntimeConfig } from '@/composables/useRuntimeConfig'
import { DEFAULT_CHAT_MODE, type ChatMode } from '@/constants/chat-modes'
import type { MessageSegment } from '@/types/chat'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    /** 可选的模式列表；为空时不渲染模式选择区 */
    modes?: ChatMode[]
    /** 当前选中的 select_model */
    mode?: number
    /** 是否正在生成回答：为真时把发送按钮换成停止按钮 */
    sending?: boolean
    /** 是否显示「语音面试」按钮（只有面试间打开） */
    showVoiceToggle?: boolean
    /** 语音面试是否已开启，用于按钮的选中态 */
    voiceEnabled?: boolean
    /** 是否显示「结束面试」按钮（只在模拟面试模式且本会话已有面试记录时打开） */
    showFinishButton?: boolean
    /** 结束面试请求进行中 */
    finishing?: boolean
    /**
     * 输入框的占位文案。
     *
     * 默认是"输入你的回答…"。但**还没有任何会话**时输入框是禁用的（没有会话就没地方存消息），
     * 这时上层会换成引导文案——否则用户面对一个点不进去、打不了字的输入框，
     * 只会以为界面坏了。部署成演示环境后，每个新访客都会撞上这个困惑。
     */
    placeholder?: string
  }>(),
  {
    modes: () => [],
    mode: DEFAULT_CHAT_MODE,
    sending: false,
    showVoiceToggle: false,
    voiceEnabled: false,
    showFinishButton: false,
    finishing: false,
    placeholder: '输入你的回答...'
  }
)

const emit = defineEmits<{
  send: [text: string, segments: MessageSegment[]]
  stop: []
  /** 点击底部控制带里的「语音面试」按钮 */
  toggleVoice: []
  /** 点击「结束面试」 */
  finishInterview: []
  'update:mode': [value: number]
}>()

// 后端 resource_type 到消息附件类型的映射
const SEGMENT_TYPE_BY_RESOURCE_TYPE: Record<number, MessageSegment['type']> = {
  0: 'file',
  1: 'image',
  2: 'audio'
}

const text = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

// 附件入口的可用性由后端配置决定（T12.5）：演示环境可以在配置里整体关掉上传。
// 这里直接读那个**模块级单例**（已经加载过就不再请求），不用再往上层逐级传 prop——
// 这个组件被三个房间复用，加一个 prop 就要动 ChatWindow 和三个页面。
// 拉取失败按"可用"处理，真正的拦截在后端上传接口上。
const { runtimeConfig: runtimeConfigState } = useRuntimeConfig()
const uploadAvailable = computed(
  () => runtimeConfigState.value?.features.file_upload ?? true
)

/** 已上传成功、等待随消息发送的附件 */
type PendingAttachment = {
  segment: MessageSegment
  /** 后端给的解析说明（文档才有），用于让用户立刻知道读没读到 */
  hint: string
}
const pendingAttachments = ref<PendingAttachment[]>([])

// 只要还有附件在上传中，就不让发送——避免把没传完的附件漏掉
const canSend = computed(
  () => (text.value.trim().length > 0 || pendingAttachments.value.length > 0) && !props.disabled
)

const onSend = () => {
  if (!canSend.value) {
    return
  }
  emit(
    'send',
    text.value.trim(),
    pendingAttachments.value.map((item) => item.segment)
  )
  text.value = ''
  pendingAttachments.value = []
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    onSend()
  }
}

const openFilePicker = () => {
  if (props.disabled || uploading.value) {
    return
  }
  fileInputRef.value?.click()
}

const onFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // 选完就清空，保证连续选同一个文件也能触发 change
  input.value = ''
  if (!file) {
    return
  }

  uploading.value = true
  try {
    const uploaded = await uploadFile(file)
    pendingAttachments.value.push({
      segment: {
        type: SEGMENT_TYPE_BY_RESOURCE_TYPE[uploaded.resource_type] ?? 'file',
        name: file.name,
        url: uploaded.file_path,
        resource_id: uploaded.resource_id
      },
      hint: uploaded.parse?.message ?? ''
    })
    if (uploaded.parse && !uploaded.parse.ok && !uploaded.parse.suspected_scanned) {
      // 解析失败要说出来，否则用户发完消息才发现模型没看到简历
      ElMessage.warning(uploaded.parse.message)
    }
  } catch (error) {
    ElMessage.error((error as Error).message || '附件上传失败')
  } finally {
    uploading.value = false
  }
}

const removeAttachment = (index: number) => {
  pendingAttachments.value.splice(index, 1)
}
</script>

<template>
  <section class="chat-input">
    <!-- 输入框容器：输入区在上、功能条在下，同处一个圆角框内（对齐效果图） -->
    <div class="composer">
      <!-- 待发送的附件：上传完成后在这里显示，可单独移除 -->
      <div v-if="pendingAttachments.length > 0" class="attachment-list">
        <div
          v-for="(item, index) in pendingAttachments"
          :key="item.segment.resource_id ?? index"
          class="attachment-chip">
          <el-icon><Document /></el-icon>
          <span class="attachment-chip__name">{{ item.segment.name }}</span>
          <span v-if="item.hint" class="attachment-chip__hint">{{ item.hint }}</span>
          <el-icon class="attachment-chip__remove" @click="removeAttachment(index)">
            <Close />
          </el-icon>
        </div>
      </div>

      <el-input
        v-model="text"
        class="composer__field"
        type="textarea"
        resize="none"
        :rows="3"
        :disabled="disabled"
        :placeholder="placeholder"
        @keydown="onKeydown"
      />

      <!-- 底部功能条：左侧「+ 附件 / 语音面试」，右侧「模式选择 / 发送」 -->
      <div class="composer__toolbar">
        <div class="toolbar-group">
          <el-button
            v-if="uploadAvailable"
            class="tool-btn"
            :disabled="disabled || uploading"
            :loading="uploading"
            title="选择文件"
            @click="openFilePicker">
            <el-icon><Plus /></el-icon>
          </el-button>
          <!-- 语音面试：只在面试间的「模拟面试」模式下出现 -->
          <el-button
            v-if="showVoiceToggle"
            class="tool-pill"
            :class="{ 'tool-pill--active': voiceEnabled }"
            :title="voiceEnabled ? '关闭语音面试' : '开启语音面试'"
            @click="emit('toggleVoice')">
            <el-icon><Microphone /></el-icon>
            <span>语音面试</span>
          </el-button>
          <!-- 结束面试（T7.8）：结束后会自动切到「面试复盘」并生成复盘 -->
          <el-button
            v-if="showFinishButton"
            class="tool-pill tool-pill--finish"
            :disabled="finishing"
            title="结束这场模拟面试并生成复盘"
            @click="emit('finishInterview')">
            <el-icon><CircleCheck /></el-icon>
            <span>{{ finishing ? '结束中…' : '结束面试' }}</span>
          </el-button>
        </div>

        <div class="toolbar-group toolbar-group--right">
          <ModeSelector
            v-if="modes.length > 0"
            :modes="modes"
            :model-value="mode"
            :disabled="disabled"
            @update:model-value="emit('update:mode', $event)" />
          <!-- 生成中：发送按钮切换为停止按钮；停止按钮始终可点，不受 disabled 影响 -->
          <el-button v-if="sending" class="stop-btn" @click="emit('stop')">
            <el-icon><VideoPause /></el-icon>
            <span>停止</span>
          </el-button>
          <el-button v-else class="send-btn" :disabled="!canSend" @click="onSend">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 隐藏的文件选择器：选中后先上传拿到 resource_id，再随消息一起发送 -->
    <input
      ref="fileInputRef"
      type="file"
      class="hidden-file-input"
      accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.gif,.mp3,.wav,.m4a"
      @change="onFileChange" />
  </section>
</template>

<style scoped lang="scss">
.chat-input {
  position: relative;
  /* 输入框永远贴在底部、不被压缩：可伸缩的只有上面的消息列表 */
  flex-shrink: 0;
  background: #f4f5f7;
  border-top: 1px solid #d9dce1;
  padding: 12px 0;
  display: flex;
  justify-content: center;
}

/* 圆角输入容器：输入区与功能条同处一框 */
.composer {
  width: min(1040px, calc(100vw - 560px));
  min-width: 560px;
  background: #ffffff;
  border: 1.5px solid #d5dbe4;
  border-radius: 18px;
  padding: 8px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 0.15s;

  &:focus-within {
    border-color: #4385f1;
  }
}

/* 去掉 textarea 自己的边框，让整块看起来是一个输入框 */
.composer__field :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 6px 4px;
  font-size: 15px;
  line-height: 1.6;
}

.composer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.toolbar-group--right {
  flex-shrink: 0;
  /* 模式 chips 收窄后可能与发送按钮贴太紧，留一点空隙 */
  gap: 10px;
}

.hidden-file-input {
  display: none;
}

/* 附件按钮：圆形「+」，与效果图一致 */
.tool-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid #d5dbe4;
  border-radius: 50%;
  background: #ffffff;
  color: #596272;

  &:hover,
  &:focus {
    border-color: #4385f1;
    background: #f2f7ff;
    color: #4385f1;
  }
}

/* 语音面试：胶囊按钮，和「文件」同排在左下 */
.tool-pill {
  height: 32px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #d5dbe4;
  border-radius: 16px;
  background: #ffffff;
  color: #2f4660;
  font-size: 13px;

  &:hover,
  &:focus {
    border-color: #4385f1;
    background: #f2f7ff;
    color: #2f4660;
  }
}

.tool-pill--active {
  border-color: #e06262;
  background: #fdeaea;
  color: #c33;

  &:hover,
  &:focus {
    border-color: #e06262;
    background: #fbe0e0;
    color: #c33;
  }
}

/* 结束面试：用中性偏冷的配色，和「语音面试」的红色选中态区分开 */
.tool-pill--finish {
  border-color: #cfd8e6;
  background: #f7f9fc;
  color: #2f4660;

  &:hover,
  &:focus {
    border-color: #7a9bd6;
    background: #eef4ff;
    color: #2f4660;
  }
}

/* 模式选择原本排在上方；放进底部功能条后整体收窄，避免把发送按钮挤走 */
.toolbar-group--right :deep(.mode-selector) {
  flex-wrap: nowrap;
  gap: 6px;
}

.toolbar-group--right :deep(.mode-chip) {
  padding: 5px 10px;
  font-size: 12px;
}

.send-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: #f6c700;
  color: #ffffff;

  &.is-disabled {
    background: #d1d5dc;
    color: #9ea6b3;
  }
}

/* 停止按钮比发送按钮宽（带中文文案） */
.stop-btn {
  height: 34px;
  padding: 0 14px;
  border: none;
  border-radius: 17px;
  background: #f56c6c;
  color: #ffffff;
  font-size: 14px;

  &:hover,
  &:focus {
    background: #ee5a5a;
    color: #ffffff;
  }
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  border: 1px solid #d3d9e2;
  border-radius: 8px;
  background: #f7f8fb;
  color: #4d5563;
  font-size: 13px;
  line-height: 1;
  padding: 7px 10px;
}

.attachment-chip__name {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-chip__hint {
  color: #8b93a2;
  font-size: 12px;
}

.attachment-chip__remove {
  cursor: pointer;
  color: #9ea6b3;

  &:hover {
    color: #f56c6c;
  }
}

@media (max-width: 1100px) {
  .composer {
    width: calc(100vw - 130px);
    min-width: 0;
  }

  /* 窄屏下功能条放不下就换行，而不是把模式 chips 挤出可视区 */
  .composer__toolbar {
    flex-wrap: wrap;
  }

  .toolbar-group--right :deep(.mode-selector) {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}
</style>
