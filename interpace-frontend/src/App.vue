
<script setup lang="ts">
import { onMounted } from 'vue'
import { useUserStore } from './stores/user'
import { getAccessToken } from './api/token'

// 在应用根组件挂载时，尝试从本地存储恢复用户状态
onMounted(() => {
  const userStore = useUserStore()
  const token = getAccessToken()

  // 如果存在 token，就从后端获取用户信息
  if (token) {
    userStore.fetchUser()
  }
})
</script>

<template>
  <router-view />
</template>
