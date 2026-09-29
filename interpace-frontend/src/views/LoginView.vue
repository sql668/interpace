<template>
  <div class="login-page">
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
  background: v.$page-bg;
  padding: 40px 16px;
}
</style>
