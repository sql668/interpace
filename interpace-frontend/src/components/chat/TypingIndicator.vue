<script setup lang="ts">
// 等待助手首个响应片段时的加载动画：三点依次跳动。
</script>

<template>
  <span class="typing" role="status" aria-label="正在生成回答">
    <span class="typing__dot" />
    <span class="typing__dot" />
    <span class="typing__dot" />
  </span>
</template>

<style scoped lang="scss">
.typing {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 1.2em;

  &__dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background-color: #8a93a5;
    animation: typing-bounce 1.2s infinite ease-in-out;

    &:nth-child(2) {
      animation-delay: 0.15s;
    }

    &:nth-child(3) {
      animation-delay: 0.3s;
    }
  }
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.45;
  }

  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

// 系统开启“减弱动态效果”时的降级版：换成纯透明度呼吸动画，
// 仍然能看出“正在生成”，但不做位移，避免前庭类动效。
@media (prefers-reduced-motion: reduce) {
  .typing__dot {
    animation-name: typing-pulse;
  }
}

@keyframes typing-pulse {
  0%,
  100% {
    opacity: 0.25;
  }

  50% {
    opacity: 1;
  }
}
</style>
