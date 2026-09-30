<template>
  <div class="login-page">
    <!-- 回首页：登录页是公开页，用户可能只是从首页点进来看看，得给条退路 -->
    <router-link class="login-page__back" to="/">← 返回首页</router-link>
    <LoginCard />
  </div>
</template>

<script setup lang="ts">
import LoginCard from '../components/LoginCard.vue'
</script>

<style scoped lang="scss">
@use "../styles/variables" as v;

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: v.$page-bg;
  padding: 40px 16px;
}

.login-page__back {
  position: absolute;
  top: 28px;
  left: 32px;
  font-size: 14px;
  color: v.$text-muted;
  text-decoration: none;
}

.login-page__back:hover,
.login-page__back:focus-visible {
  color: v.$brand-color;
}
</style>
