<script setup lang="ts">
import { School } from '@element-plus/icons-vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { env } from '@/config/env'
import { fetchResourceBlobByPath } from '@/api/resource'
import fallbackAvatar from '@/assets/image/logo.png'
import type { NavTab } from '@/constants/nav-tabs'

// --- Props & Emits ---
defineProps<{
    activeTab: string
    tabs: NavTab[]
}>()

const emit = defineEmits<{
    tabClick: [tabKey: string]
}>()

// 品牌区可点回首页：这是"logo 点回首页"的通用约定，
// 也是工作台里唯一能回到介绍页的入口（首页是公开页，点了不会被守卫拦）。
const router = useRouter()

// --- 状态管理 ---
const userStore = useUserStore()

// 后端存的头像是 `minio://bucket/key` 路径，浏览器加载不了；而且资源接口需要
// Authorization 头，`<img src>` 带不了。所以用 axios 取成 Blob 再转临时地址。
const avatarUrl = ref('')

const releaseAvatarUrl = () => {
    if (avatarUrl.value) {
        URL.revokeObjectURL(avatarUrl.value)
        avatarUrl.value = ''
    }
}

watch(
    () => userStore.avatar,
    async (storagePath) => {
        releaseAvatarUrl()
        if (!storagePath) {
            return
        }
        try {
            avatarUrl.value = URL.createObjectURL(await fetchResourceBlobByPath(storagePath))
        } catch {
            // 取不到就回退到默认头像，不打扰用户
        }
    },
    { immediate: true }
)

onBeforeUnmount(releaseAvatarUrl)

// --- 事件处理 ---
function handleLogout() {
    // clearUser 内部会清 token 并跳转登录页；只清 token 会让 store 里仍留着上一个账号的信息
    userStore.clearUser()
}
</script>

<template>
    <header class="app-header">
        <!-- 品牌 Logo：点击回到首页 -->
        <button class="brand" type="button" title="回到首页" @click="router.push('/')">
            <span class="brand__icon">
                <el-icon><School /></el-icon>
            </span>
            <span class="brand__name">{{ env.appTitle }}</span>
        </button>

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
                    <el-avatar :size="36" :src="avatarUrl">
                        <!-- 没头像或加载失败时用本地默认图，不再依赖第三方地址 -->
                        <img :src="fallbackAvatar" alt="默认头像" />
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
    /* 它是个 button（为了能点回首页），所以要把浏览器默认样式清掉 */
    padding: 0;
    border: none;
    background: transparent;
    font: inherit;
    cursor: pointer;
    text-align: left;
}

.brand:hover .brand__name,
.brand:focus-visible .brand__name {
    color: v.$brand-color;
}

.brand:focus-visible {
    outline: 2px solid v.$brand-color;
    outline-offset: 4px;
    border-radius: 6px;
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
