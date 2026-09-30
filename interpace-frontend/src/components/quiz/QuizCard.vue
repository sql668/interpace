<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import QuizQuestionBlock from './QuizQuestionBlock.vue'
import { createNote } from '@/api/note'
import { getQuizPaperDetail, submitQuizPaper } from '@/api/quiz'
import type { QuizPaperDetail, QuizQuestionItem } from '@/types/quiz'

const props = defineProps<{
  /** 卷子 ID，来自「按会话列出卷子」或流式结束时的 quiz_paper_id */
  paperId: number
}>()

const emit = defineEmits<{
  explainTopics: [topics: string[]]
}>()

const loading = ref(true)
const submitting = ref(false)
const paper = ref<QuizPaperDetail | null>(null)
// 已提交但未评分（评分失败后重试的场景）
const submitted = ref(false)
const graded = ref(false)
const totalScore = ref<number | null>(null)
const weakTopics = ref<string[]>([])
const savingNote = ref(false)

// order_index -> 用户作答；用响应式对象，题目块用 v-model 读写。
const answers = reactive<Record<number, string>>({})

const questions = computed<QuizQuestionItem[]>(() => paper.value?.questions ?? [])

// 已评分的题目得分平均分：刷新回来看历史时用得上（总分只在提交响应里有）。
const averageScore = computed(() => {
  const scores = questions.value
    .map((item) => item.score)
    .filter((score): score is number => typeof score === 'number')
  if (!scores.length) return null
  return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
})

const displayScore = computed(() => totalScore.value ?? averageScore.value)

// 笔记正文是富文本 HTML，题目与解析来自模型输出，必须转义后再拼，
// 否则回答里的尖括号会被当成 HTML 标签渲染。
const escapeHtml = (text: string): string =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const loadPaper = async () => {
  loading.value = true
  try {
    const detail = await getQuizPaperDetail(props.paperId)
    paper.value = detail
    for (const question of detail.questions) {
      answers[question.order_index] = question.user_answer ?? ''
    }
    // 刷新回到已评分的卷子：直接进结果态，不再让人重做一遍。
    graded.value = detail.status === 2
    submitted.value = detail.status === 1
  } catch {
    ElMessage.error('题库加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  if (submitting.value) return
  submitting.value = true
  try {
    const result = await submitQuizPaper(props.paperId, {
      answers: questions.value.map((question) => ({
        order_index: question.order_index,
        answer: answers[question.order_index] ?? ''
      }))
    })
    totalScore.value = result.total_score
    weakTopics.value = result.weak_topics
    if (paper.value) {
      paper.value.questions = result.questions
      paper.value.status = result.status
    }
    graded.value = true
    submitted.value = false
    ElMessage.success('评分完成')
  } catch (error) {
    const message = error instanceof Error ? error.message : '提交失败，请稍后重试'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

const handleSaveToNote = () => {
  // 注意：不把入口消息的正文（原始 JSON）存进笔记。
  // 这里用已有的 `POST /notes` 存一份**人读得懂**的错题笔记：得分 + 薄弱点 + 逐题解析。
  void saveGradingNote()
}

const buildNoteHtml = (): string => {
  const meta = [paper.value?.target_job || '未指定岗位']
  if (paper.value?.difficulty) meta.push(paper.value.difficulty)
  meta.push(`${questions.value.length} 题`)

  const parts: string[] = []
  parts.push(`<h3>刷题记录 · ${escapeHtml(meta.join(' · '))}</h3>`)
  parts.push(`<p><strong>得分：</strong>${displayScore.value ?? '—'}</p>`)
  if (weakTopics.value.length) {
    parts.push(`<p><strong>薄弱点：</strong>${escapeHtml(weakTopics.value.join('、'))}</p>`)
  }
  parts.push('<h4>逐题解析</h4>')
  for (const question of questions.value) {
    parts.push(
      `<p><strong>${question.order_index}. ${escapeHtml(question.question)}</strong><br/>` +
        `得分：${question.score ?? '—'}<br/>` +
        `${escapeHtml(question.analysis || '（无解析）')}</p>`
    )
  }
  return parts.join('')
}

const saveGradingNote = async () => {
  if (savingNote.value) return
  savingNote.value = true
  try {
    const title = `刷题笔记 · ${paper.value?.target_job || '综合'} ${paper.value?.difficulty ?? ''}`.trim()
    // source_type 用 0（手写）：笔记来源枚举里没有「来自刷题」这一项，
    // 不为它单独扩枚举；真要区分来源时再统一加取值。
    await createNote({ title, content: buildNoteHtml(), source_type: 0 })
    ElMessage.success('已存入笔记')
  } catch {
    ElMessage.error('存入笔记失败，请稍后重试')
  } finally {
    savingNote.value = false
  }
}

const handleExplainTopics = () => {
  if (!weakTopics.value.length) return
  emit('explainTopics', weakTopics.value)
}

onMounted(loadPaper)
</script>

<template>
  <section class="quiz-card">
    <header class="quiz-card__head">
      <span class="quiz-card__title">刷题练习</span>
      <span class="quiz-card__meta">
        {{ paper?.target_job || '未指定岗位' }}
        <template v-if="paper?.difficulty"> · {{ paper.difficulty }}</template>
        · {{ paper?.question_count ?? 0 }} 题
      </span>
    </header>

    <p v-if="loading" class="quiz-card__hint">题库加载中…</p>

    <template v-else-if="questions.length">
      <QuizQuestionBlock
        v-for="question in questions"
        :key="question.id"
        :index="question.order_index"
        :question="question"
        :graded="graded"
        :disabled="submitting"
        v-model:answer="answers[question.order_index]" />

      <!-- 结果区：总分 / 薄弱点 / 跨模块入口 -->
      <div v-if="graded" class="quiz-result">
        <p class="quiz-result__score">
          得分
          <strong>{{ displayScore ?? '—' }}</strong>
          <span v-if="displayScore !== null" class="quiz-result__unit">/ 100</span>
        </p>
        <p v-if="weakTopics.length" class="quiz-result__topics">
          <span class="topics-label">薄弱点</span>
          <span v-for="topic in weakTopics" :key="topic" class="topic-chip">{{ topic }}</span>
        </p>
        <div class="quiz-result__actions">
          <button
            v-if="weakTopics.length"
            type="button"
            class="action action--primary"
            @click="handleExplainTopics">
            针对薄弱点讲一讲
          </button>
          <button type="button" class="action" :disabled="savingNote" @click="handleSaveToNote">
            {{ savingNote ? '保存中…' : '存入笔记' }}
          </button>
        </div>
      </div>

      <!-- 未评分：提交按钮。已提交未评分时文案改为重新评分（评分失败重试） -->
      <div v-else class="quiz-actions">
        <button
          type="button"
          class="action action--primary"
          :disabled="submitting"
          @click="handleSubmit">
          {{ submitting ? '评分中…' : submitted ? '重新评分' : '提交并评分' }}
        </button>
      </div>
    </template>

    <p v-else class="quiz-card__hint">这份题库没有题目</p>
  </section>
</template>

<style scoped lang="scss">
.quiz-card {
  margin-top: 12px;
  border: 1px solid #e2d6ad;
  border-radius: 12px;
  background: #fffdf6;
  padding: 14px 16px;
}

.quiz-card__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #efe3c2;
}

.quiz-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #8a6d00;
}

.quiz-card__meta {
  font-size: 13px;
  color: #9d8b57;
}

.quiz-card__hint {
  margin: 10px 0 0;
  font-size: 14px;
  color: #9ea6b4;
}

.quiz-result {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #efe3c2;
}

.quiz-result__score {
  margin: 0 0 8px;
  font-size: 14px;
  color: #5a6472;
}

.quiz-result__score strong {
  font-size: 22px;
  color: #d97706;
}

.quiz-result__unit {
  font-size: 12px;
  color: #9ea6b4;
}

.quiz-result__topics {
  margin: 0 0 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.topics-label {
  font-size: 13px;
  color: #5a6472;
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

.quiz-actions,
.quiz-result__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.action {
  border: 1px solid #e6d9ae;
  border-radius: 8px;
  background: #fffaf0;
  color: #8a6d00;
  font-size: 14px;
  padding: 8px 14px;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.action--primary {
  border-color: #4385f1;
  background: #4385f1;
  color: #fff;
}
</style>
