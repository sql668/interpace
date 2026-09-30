<script setup lang="ts">
import { computed } from 'vue'
import type { QuizQuestionItem } from '@/types/quiz'

const props = defineProps<{
  /** 题目序号，从 1 开始 */
  index: number
  question: QuizQuestionItem
  /** 是否已评分：评分后由输入框切换为「得分 + 解析」 */
  graded: boolean
  /** 用户作答文本（v-model:answer） */
  answer: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:answer': [value: string]
}>()

// 受控输入：写回时通过 update:answer 交给父组件，父组件统一持有答案表。
const localAnswer = computed({
  get: () => props.answer,
  set: (value: string) => emit('update:answer', value)
})
</script>

<template>
  <section class="quiz-question">
    <p class="stem"><span class="index">{{ index }}.</span>{{ question.question }}</p>

    <!-- 已评分：展示得分与逐题解析，不再允许修改 -->
    <template v-if="graded">
      <p class="score">
        得分
        <strong>{{ question.score ?? '—' }}</strong>
        <span v-if="question.score !== null" class="score-unit">/ 100</span>
      </p>
      <p v-if="question.analysis" class="analysis">{{ question.analysis }}</p>
      <p v-else class="analysis analysis--empty">这道题没有返回解析</p>
    </template>

    <!-- 未评分：输入作答 -->
    <template v-else>
      <textarea
        v-model="localAnswer"
        class="answer-input"
        rows="4"
        :disabled="disabled"
        placeholder="写下你的答案，答不上来可以直接留空"></textarea>
    </template>
  </section>
</template>

<style scoped lang="scss">
.quiz-question {
  padding: 12px 0;
  border-bottom: 1px dashed #dde2ea;

  &:last-child {
    border-bottom: none;
  }
}

.stem {
  margin: 0 0 8px;
  font-size: 16px;
  line-height: 1.6;
  color: #2f3642;
  white-space: pre-wrap;
  word-break: break-word;
}

.index {
  margin-right: 6px;
  font-weight: 600;
  color: #4385f1;
}

.score {
  margin: 0 0 6px;
  font-size: 14px;
  color: #5a6472;
}

.score strong {
  font-size: 18px;
  color: #d97706;
}

.score-unit {
  color: #9ea6b4;
  font-size: 12px;
}

.analysis {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #4a5462;
  white-space: pre-wrap;
  word-break: break-word;
}

.analysis--empty {
  color: #9ea6b4;
}

.answer-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #d5dbe4;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
  color: #2f3642;
  background: #fff;
  resize: vertical;

  &:focus {
    outline: none;
    border-color: #4385f1;
  }

  &:disabled {
    background: #f6f7f9;
    cursor: not-allowed;
  }
}
</style>
