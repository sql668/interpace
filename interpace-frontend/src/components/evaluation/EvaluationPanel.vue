<script setup lang="ts">
/**
 * 面试复盘面板（T8.5）。
 *
 * 两种输入都能出复盘：
 * - **问答复盘**：直接读这场面试已落库的问答记录（快）；
 * - **录音复盘**：上传一段真实面试录音，后端转写后再评测（T8.3）。
 *
 * 结果区给出总结 / 薄弱点 / 改进建议，并接上流程图要求的两个出口：
 * 「针对薄弱点讲一讲」（跳知识精讲）与「存入笔记」。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, Upload } from '@element-plus/icons-vue'
import {
  generateInterviewEvaluation,
  generateInterviewEvaluationFromAudio,
  getInterviewEvaluation
} from '@/api/chat'
import { createNote } from '@/api/note'
import { uploadFile } from '@/api/upload'
import type { InterviewEvaluation } from '@/types/chat'
import { notifyError } from '@/utils/errorMessage'

const props = defineProps<{
  /** 当前会话里可复盘的面试记录 ID（一场面试一个，取最近的） */
  interviewId: number | null
}>()

const emit = defineEmits<{
  /** 把薄弱点交给房间，切到知识精讲继续讲 */
  explainTopics: [topics: string[]]
}>()

const loading = ref(false)
const generating = ref(false)
const uploading = ref(false)
const savingNote = ref(false)
const evaluation = ref<InterviewEvaluation | null>(null)
const transcript = ref('')
const notGenerated = ref(false)

/** 面板只对「有面试记录」的会话可用 */
const available = computed(() => props.interviewId !== null)

const sourceLabel = computed(() =>
  evaluation.value?.source === 1 ? '来自上传的录音' : '来自面试问答记录'
)

const load = async () => {
  evaluation.value = null
  transcript.value = ''
  notGenerated.value = false
  if (!props.interviewId) {
    return
  }
  loading.value = true
  try {
    const data = await getInterviewEvaluation(props.interviewId)
    // 期间可能已经生成了复盘（例如「结束面试」触发的自动生成）：
    // 这时不要用「还没生成」覆盖掉刚拿到的结果，否则界面会闪一下。
    if (evaluation.value) {
      return
    }
    if (data.evaluation) {
      evaluation.value = data.evaluation
    } else {
      // 「还没生成」是正常状态：后端返回 200 + null，不产生错误响应，
      // 也就不会触发全局拦截器的错误提示（这点踩过坑，见 T8.2 备注）。
      notGenerated.value = true
    }
  } catch {
    // 到这里才是真错误（网络、500、面试记录不存在）
    ElMessage.error('读取复盘失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 切会话或切模式时重新拉一次：避免把上一场的复盘显示在这一场下面
watch(() => props.interviewId, load, { immediate: true })

const handleGenerate = async () => {
  if (!props.interviewId || generating.value) {
    return
  }
  generating.value = true
  try {
    const data = await generateInterviewEvaluation(props.interviewId)
    evaluation.value = data.evaluation
    transcript.value = ''
    notGenerated.value = false
    ElMessage.success(data.message)
  } catch (error) {
    notifyError(error, '生成复盘失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

const audioInputRef = ref<HTMLInputElement | null>(null)

const openAudioPicker = () => {
  if (!props.interviewId || uploading.value) {
    return
  }
  audioInputRef.value?.click()
}

const handleAudioChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !props.interviewId) {
    return
  }

  uploading.value = true
  try {
    // 先上传拿到 resource_id，再让后端转写 + 复盘（转写可能要等十几秒到更久）
    const uploaded = await uploadFile(file)
    const data = await generateInterviewEvaluationFromAudio(
      props.interviewId,
      uploaded.resource_id
    )
    evaluation.value = data.evaluation
    transcript.value = data.transcript
    notGenerated.value = false
    ElMessage.success(data.message)
  } catch (error) {
    notifyError(error, '录音复盘失败，请稍后重试')
  } finally {
    uploading.value = false
  }
}

const handleExplainTopics = () => {
  const topics = evaluation.value?.weak_topics ?? []
  if (!topics.length) {
    return
  }
  emit('explainTopics', topics)
}

const buildNoteHtml = (): string => {
  const ev = evaluation.value
  if (!ev) {
    return ''
  }
  const parts: string[] = []
  parts.push('<h3>面试复盘</h3>')
  parts.push(`<p>${escapeHtml(ev.summary)}</p>`)
  if (ev.weak_topics.length) {
    parts.push(`<h4>薄弱点</h4><p>${ev.weak_topics.map(escapeHtml).join('、')}</p>`)
  }
  if (ev.suggestions.length) {
    parts.push('<h4>改进建议</h4>')
    parts.push(`<ol>${ev.suggestions.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ol>`)
  }
  return parts.join('')
}

/** 笔记正文是富文本，模型输出必须先转义再拼，否则尖括号会被当标签渲染 */
const escapeHtml = (text: string): string =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const handleSaveToNote = async () => {
  if (!evaluation.value || savingNote.value) {
    return
  }
  savingNote.value = true
  try {
    await createNote({
      title: `面试复盘 · ${new Date().toLocaleDateString('zh-CN')}`,
      content: buildNoteHtml(),
      source_type: 0
    })
    ElMessage.success('已存入笔记')
  } catch {
    ElMessage.error('存入笔记失败，请稍后重试')
  } finally {
    savingNote.value = false
  }
}

// 供父组件在「结束面试」后主动触发一次生成（模板 ref 调用）
defineExpose({
  generate: handleGenerate,
  reload: load
})
</script>

<template>
  <section class="evaluation">
    <header class="evaluation__head">
      <span class="evaluation__title">面试复盘</span>
      <span v-if="evaluation" class="evaluation__meta">
        {{ sourceLabel }} · 输入规模 {{ evaluation.qa_count }}
      </span>
    </header>

    <p v-if="!available" class="evaluation__hint">
      这个会话里还没有面试记录。先去「模拟面试」模式做一场，再回来复盘。
    </p>

    <p v-else-if="loading" class="evaluation__hint">正在读取复盘…</p>

    <template v-else>
      <div class="evaluation__actions">
        <button type="button" class="btn btn--primary" :disabled="generating" @click="handleGenerate">
          {{ generating ? '生成中…' : evaluation ? '按问答重新复盘' : '生成复盘' }}
        </button>
        <button type="button" class="btn" :disabled="uploading" @click="openAudioPicker">
          <el-icon><Upload /></el-icon>
          {{ uploading ? '转写中…' : '上传录音复盘' }}
        </button>
        <span class="evaluation__tip">
          <el-icon><Microphone /></el-icon>
          录音支持 wav / mp3 / m4a，后端会先转写成文字再评测
        </span>
      </div>

      <!-- 有复盘结果：总结 + 薄弱点 + 建议 -->
      <template v-if="evaluation">
        <p class="evaluation__summary">{{ evaluation.summary }}</p>

        <div v-if="evaluation.weak_topics.length" class="evaluation__topics">
          <span class="evaluation__label">薄弱点</span>
          <span v-for="topic in evaluation.weak_topics" :key="topic" class="topic-chip">
            {{ topic }}
          </span>
          <button type="button" class="btn btn--small" @click="handleExplainTopics">
            针对薄弱点讲一讲
          </button>
        </div>

        <ol v-if="evaluation.suggestions.length" class="evaluation__suggestions">
          <li v-for="(item, index) in evaluation.suggestions" :key="index">{{ item }}</li>
        </ol>

        <details v-if="transcript" class="evaluation__transcript">
          <summary>AI 听到的内容（点开核对转写）</summary>
          <p>{{ transcript }}</p>
        </details>

        <div class="evaluation__footer">
          <button type="button" class="btn" :disabled="savingNote" @click="handleSaveToNote">
            {{ savingNote ? '保存中…' : '存入笔记' }}
          </button>
        </div>
      </template>

      <p v-else-if="notGenerated" class="evaluation__hint">
        这场面试还没有复盘，点上面的按钮生成一份。
      </p>
    </template>

    <!-- 隐藏的录音选择器：选中后先上传，再由后端转写 + 复盘 -->
    <input
      ref="audioInputRef"
      type="file"
      class="hidden-input"
      accept=".wav,.mp3,.m4a,.aac,.ogg,.pcm"
      @change="handleAudioChange" />
  </section>
</template>

<style scoped lang="scss">
.evaluation {
  border: 1px solid #dfe6f1;
  border-radius: 12px;
  background: #fbfcff;
  padding: 14px 16px;
  margin: 10px 16px 0;
  /* 与语音面板同样的策略：自己滚，不把下面的输入框挤出屏幕 */
  flex-shrink: 0;
  max-height: 52vh;
  overflow-y: auto;
}

.evaluation__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e6ecf5;
}

.evaluation__title {
  font-size: 15px;
  font-weight: 600;
  color: #2f4660;
}

.evaluation__meta,
.evaluation__hint,
.evaluation__tip {
  font-size: 13px;
  color: #8b93a2;
}

.evaluation__hint {
  margin: 10px 0 0;
  line-height: 1.6;
}

.evaluation__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0;
}

.evaluation__tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.evaluation__summary {
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.8;
  color: #2f3642;
  white-space: pre-wrap;
}

.evaluation__topics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.evaluation__label {
  font-size: 13px;
  color: #8b93a2;
}

.topic-chip {
  border: 1px solid #f0cfa1;
  border-radius: 999px;
  background: #fff5e6;
  color: #b3641a;
  font-size: 12px;
  line-height: 1;
  padding: 4px 10px;
}

.evaluation__suggestions {
  margin: 0 0 10px;
  padding-left: 20px;
  font-size: 14px;
  line-height: 1.8;
  color: #3c4552;
}

.evaluation__transcript {
  font-size: 13px;
  color: #5a6472;

  summary {
    cursor: pointer;
    color: #4385f1;
  }

  p {
    margin: 8px 0 0;
    line-height: 1.7;
    white-space: pre-wrap;
    background: #f4f6fa;
    border-radius: 8px;
    padding: 10px 12px;
  }
}

.evaluation__footer {
  margin-top: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #cfd8e6;
  border-radius: 8px;
  background: #fff;
  color: #2f4660;
  font-size: 13px;
  padding: 7px 12px;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.btn--primary {
  border-color: #4385f1;
  background: #4385f1;
  color: #fff;
}

.btn--small {
  padding: 5px 10px;
  font-size: 12px;
}

.hidden-input {
  display: none;
}
</style>
