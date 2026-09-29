<script setup lang="ts">
import { School } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { clearTokens } from '../../api/token'
import { env } from '@/config/env'

// --- 类型定义 ---
type NavTab = {
    key: string
    label: string
}

// --- Props & Emits ---
defineProps<{
    activeTab: string
    tabs: NavTab[]
}>()

const emit = defineEmits<{
    tabClick: [tabKey: string]
}>()

// --- 状态管理 ---
const router = useRouter()
const userStore = useUserStore()
const baseURL = import.meta.env.VITE_API_BASE_URL

// --- 事件处理 ---
function handleLogout() {
    clearTokens() // clearTokens 会自动调用 userStore.clearUser()
    router.replace('/login')
}
</script>

<template>
    <header class="app-header">
        <!-- 品牌 Logo -->
        <div class="brand">
            <span class="brand__icon">
                <el-icon><School /></el-icon>
            </span>
            <span class="brand__name">{{ env.appTitle }}</span>
        </div>

        <!-- 导航标签 -->
        <el-space :size="30">
            <el-button
                v-for="tab in tabs"
                :key="tab.key"
                class="tab-btn"
                :class="{ 'tab-btn--active': activeTab === tab.key }"
                @click="emit('tabClick', tab.key)">
                {{ tab.label }}
            </el-button>
        </el-space>

        <!-- 右侧用户操作区 -->
        <div class="header-actions">
            <el-dropdown v-if="userStore.isLoggedIn">
                <div class="user-profile">
                    <el-avatar
                        :size="36"
                        :src="userStore.avatar ? `${baseURL}/${userStore.avatar}` : ''">
                        <!-- Fallback for avatar -->
                        <img
                            src="https://cube.elemecdn.com/e/fd/0fc7d20532fdaf769a25683617711png.png" />
                    </el-avatar>
                    <span class="username">{{ userStore.username }}</span>
                </div>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </div>
    </header>
</template>

<style scoped lang="scss">
@use '../../styles/variables' as v;

.app-header {
    height: 72px;
    border-bottom: 1px solid v.$header-border;
    background-color: v.$header-bg;
    padding: 0 20px;
    display: flex;
    align-items: center;
    gap: 30px;
}
:deep(.el-space) {
    margin-left: 88px !important;
}
.header-actions {
    margin-left: auto;
}

.user-profile {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
}

.username {
    font-size: 16px;
    font-weight: 600;
    color: #30353e;
}

.brand {
    min-width: 180px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.brand__icon {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background-color: v.$brand-color;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

.brand__name {
    font-size: 18px;
    line-height: 1;
    font-weight: 700;
    color: #30353e;
    letter-spacing: 0.2px;
}

.tab-btn {
    width: 80px;
    height: 40px;
    border: none;
    border-radius: 8px;
    background: v.$tab-bg;
    color: #434952;
    font-size: 17px;
    font-weight: 600;

    &.tab-btn--active {
        background: v.$tab-active-bg;
        box-shadow: v.$tab-active-shadow;
    }
}
</style>
