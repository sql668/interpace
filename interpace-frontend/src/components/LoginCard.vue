<template>
    <div class="login-card">
        <!-- ... 品牌标题部分保持不变 ... -->
        <div class="brand">
            <div class="brand-icon" aria-hidden="true">
                <img class="brand-icon__img" :src="logoUrl" alt="logo" />
            </div>
            <div class="brand-title">学面通AI</div>
        </div>

        <el-upload
            class="avatar-uploader"
            action="#"
            :show-file-list="false"
            :before-upload="beforeAvatarUpload"
            :http-request="handleAvatarSelect"
            :disabled="!isRegister">
            <img v-if="avatarUrl" :src="avatarUrl" class="avatar" />
            <div v-else class="avatar-uploader-icon">
                <div class="avatar-placeholder"></div>
                <div v-show="isRegister" class="upload-icon-wrapper">
                    <el-icon><CameraFilled /></el-icon>
                </div>
            </div>
        </el-upload>

        <!-- ... Tabs 和 表单部分保持不变 ... -->
        <el-tabs v-model="activeTab" class="tabs" type="card" stretch @tab-change="handleTabChange">
            <el-tab-pane label="登录" name="login" />
            <el-tab-pane label="注册" name="register" />
        </el-tabs>

        <el-form ref="formRef" class="form" :model="form" :rules="rules" label-position="top">
            <el-form-item prop="account">
                <el-input
                    v-model.trim="form.account"
                    placeholder="用户名或邮箱"
                    size="large"
                    :prefix-icon="User" />
            </el-form-item>

            <el-form-item prop="password">
                <el-input
                    v-model.trim="form.password"
                    placeholder="密码"
                    size="large"
                    show-password
                    :prefix-icon="Lock" />
            </el-form-item>

            <el-form-item v-if="isRegister" prop="confirm">
                <el-input
                    v-model.trim="form.confirm"
                    placeholder="确认密码"
                    size="large"
                    show-password
                    :prefix-icon="Lock" />
            </el-form-item>
        </el-form>

        <el-button
            class="submit"
            type="warning"
            size="large"
            @click="handleSubmit"
            :loading="isSubmitting">
            {{ isRegister ? '注册' : '登录' }}
        </el-button>
    </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules, UploadProps, UploadRequestOptions } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Lock, User, CameraFilled } from '@element-plus/icons-vue'
import { login, register } from '../api/auth'
import { setTokens } from '../api/token'
import { useUserStore } from '../stores/user'
import { uploadAvatar } from '../api/upload' // 导入新的上传函数
import logoUrl from '../assets/image/logo.png'

// --- 响应式状态定义 ---
const activeTab = ref<'login' | 'register'>('login')
const isRegister = computed(() => activeTab.value === 'register')
const formRef = ref<FormInstance>()
const router = useRouter()
const route = useRoute()
const userStore = useUserStore() // 获取 user store 实例
const isSubmitting = ref(false) // 防止重复提交

const form = reactive({
    account: '',
    password: '',
    confirm: '',
})

// 用于预览的头像 URL (可以是本地 ObjectURL 或远程 URL)
const avatarUrl = ref('')
// 存储用户选择的头像文件对象
const avatarFile = ref<File | null>(null)

// --- 表单校验规则 (保持不变) ---
const emailRegex = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
const usernameRegex = /^[A-Za-z0-9_]{3,20}$/
const passwordRegex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,72}$/
const rules = computed<FormRules>(() => ({
    account: [
        { required: true, message: '请输入用户名或邮箱', trigger: 'blur' },
        {
            validator: (_rule, value, callback) => {
                if (!value) return callback()
                const ok = emailRegex.test(value) || usernameRegex.test(value)
                callback(ok ? undefined : new Error('请输入正确的用户名或邮箱格式'))
            },
            trigger: 'blur',
        },
    ],
    password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        {
            validator: (_rule, value, callback) => {
                if (!value) return callback()
                const ok = passwordRegex.test(value)
                callback(ok ? undefined : new Error('密码需包含字母和数字，长度 8-72 位'))
            },
            trigger: 'blur',
        },
    ],
    confirm: isRegister.value
        ? [
              { required: true, message: '请再次输入密码', trigger: 'blur' },
              {
                  validator: (_rule, value, callback) => {
                      if (!value) return callback()
                      callback(
                          value === form.password ? undefined : new Error('两次输入的密码不一致'),
                      )
                  },
                  trigger: 'blur',
              },
          ]
        : [],
}))

// --- 事件处理 ---

// 切换 Tab 时重置状态
function handleTabChange() {
    form.password = ''
    form.confirm = ''
    avatarUrl.value = ''
    avatarFile.value = null
    formRef.value?.clearValidate()
}

// 提交表单：登录或注册
async function handleSubmit() {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid || isSubmitting.value) return

    isSubmitting.value = true
    try {
        if (isRegister.value) {
            // --- 执行新的注册流程 ---
            // 1. 注册用户
            await register({ username: form.account, password: form.password })
            ElMessage.success('账号注册成功！')

            // 2. 自动登录以获取 Token
            const token = await login({ username: form.account, password: form.password })
            setTokens(token)

            // 3. 如果有头像，则上传头像
            if (avatarFile.value) {
                const res = await uploadAvatar(avatarFile.value)
                userStore.updateUserAvatar(res.avatar_url) // 更新全局状态
            }

            // 4. 获取用户信息并跳转
            await userStore.fetchUser() // 拉取并更新用户信息
            ElMessage.success('欢迎您！已成功登录')
            const redirect =
                typeof route.query.redirect === 'string' ? route.query.redirect : '/interview-room'
            router.replace(redirect)
        } else {
            // --- 执行登录流程 ---
            const token = await login({ username: form.account, password: form.password })
            setTokens(token)
            await userStore.fetchUser() // 拉取并更新用户信息
            ElMessage.success('登录成功')
            const redirect =
                typeof route.query.redirect === 'string' ? route.query.redirect : '/interview-room'
            router.replace(redirect)
        }
    } catch (err: any) {
        const msg =
            err?.response?.data?.message ||
            err?.response?.data?.detail ||
            err?.message ||
            '请求失败，请稍后再试'
        ElMessage.error(msg)
    } finally {
        isSubmitting.value = false
    }
}

// --- 头像上传相关 ---

// 文件上传前的校验
const beforeAvatarUpload: UploadProps['beforeUpload'] = (rawFile) => {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif']
    if (!allowedTypes.includes(rawFile.type)) {
        ElMessage.error('头像必须是 JPG, PNG, 或 GIF 格式!')
        return false
    }
    if (rawFile.size / 1024 / 1024 > 10) {
        ElMessage.error('头像大小不能超过 10MB!')
        return false
    }
    return true
}

// 覆盖 el-upload 的默认上传行为，只在前端保存文件和预览
function handleAvatarSelect(options: UploadRequestOptions) {
    avatarFile.value = options.file
    // 创建本地预览 URL
    avatarUrl.value = URL.createObjectURL(options.file)
}
</script>

<style scoped lang="scss">
/* ... 样式部分保持不变 ... */
@use '../styles/variables' as v;

.login-card {
    --card-bg: #ffffff;
    --text-main: #{v.$text-main};
    --text-muted: #{v.$text-muted};
    --text-placeholder: #{v.$text-placeholder};
    --border: #{v.$border-color};
    --brand: #{v.$brand-color};
    --shadow: #{v.$card-shadow};
    width: 480px;
    border-radius: 16px;
    background: var(--card-bg);
    box-shadow: var(--shadow);
    padding: 30px 36px 36px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 2px;
    }

    .brand-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: transparent;

        &__img {
            width: 30px;
            height: 30px;
            display: block;
        }
    }

    .brand-title {
        font-size: 20px;
        font-weight: 600;
        color: var(--text-main);
        letter-spacing: 0.5px;
    }

    .avatar-uploader {
        position: relative;
        .avatar {
            width: 78px;
            height: 78px;
            border-radius: 50%;
            object-fit: cover;
        }
        .avatar-placeholder {
            width: 78px;
            height: 78px;
            border-radius: 50%;
            background:
                radial-gradient(
                    circle at 30% 25%,
                    rgba(255, 255, 255, 0.8),
                    rgba(255, 255, 255, 0) 45%
                ),
                linear-gradient(
                    180deg,
                    #92c9f0 0%,
                    #bcdff6 45%,
                    #f2d7b3 46%,
                    #e7b07a 70%,
                    #7eb3e6 100%
                );
            position: relative;
            overflow: hidden;

            &::after {
                content: '';
                position: absolute;
                left: 50%;
                bottom: -6px;
                width: 26px;
                height: 54px;
                background: linear-gradient(180deg, #f1c28f 0%, #d98a4f 100%);
                transform: translateX(-50%);
                border-radius: 8px 8px 0 0;
                box-shadow: inset 0 4px 0 rgba(255, 255, 255, 0.25);
            }
        }

        .upload-icon-wrapper {
            position: absolute;
            bottom: 0;
            right: 0;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--brand);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid white;
            pointer-events: none; // 点击事件穿透
        }
    }

    .tabs {
        width: 160px;
    }

    .form {
        width: 100%;
        margin-top: 4px;
    }

    :deep(.el-tabs__header) {
        margin: 0;
        border-bottom: none;
        box-shadow: none;
    }

    :deep(.el-tabs__nav) {
        width: 100%;
        display: flex;
        justify-content: center;
        gap: 24px;
        border: none;
        background: transparent;
    }

    :deep(.el-tabs__item) {
        border: none;
        padding: 0 6px 6px;
        font-size: 15px;
        color: var(--text-muted);
        position: relative;
        background: transparent;
        box-shadow: none;
    }

    :deep(.el-tabs__item.is-active) {
        color: var(--brand);
        font-weight: 600;
        border: none;
        background: transparent;
        box-shadow: none;
    }

    :deep(.el-tabs__item.is-active::after) {
        content: '';
        position: absolute;
        left: 50%;
        bottom: 0;
        width: 22px;
        height: 3px;
        background: var(--brand);
        transform: translateX(-50%);
        border-radius: 2px;
    }

    :deep(.el-tabs__active-bar) {
        display: none;
    }

    :deep(.el-tabs--card > .el-tabs__header) {
        border-bottom: none;
    }

    :deep(.el-tabs--card > .el-tabs__header .el-tabs__item) {
        border: none;
    }

    :deep(.el-tabs--card > .el-tabs__header .el-tabs__nav) {
        border: none;
        box-shadow: none;
        background: transparent;
    }

    :deep(.el-tabs--card > .el-tabs__header .el-tabs__item.is-active) {
        border: none;
    }

    :deep(.el-form-item) {
        margin-bottom: 14px;
    }

    :deep(.el-input__wrapper) {
        height: 46px;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: none;
    }

    :deep(.el-input__wrapper.is-focus) {
        border-color: #f3c27a;
        box-shadow: none;
    }

    :deep(.el-input__inner) {
        font-size: 14px;
        color: var(--text-main);
    }

    :deep(.el-input__inner::placeholder) {
        color: var(--text-placeholder);
    }

    :deep(.el-input__prefix) {
        color: #98a1ab;
    }

    :deep(.el-form-item__error) {
        font-size: 12px;
        padding-left: 4px;
    }

    .submit {
        width: 100%;
        height: 46px;
        border-radius: 10px;
        font-size: 16px;
        font-weight: 600;
        margin-top: 6px;
        letter-spacing: 1px;
    }
}

@media (max-width: 720px) {
    .login-card {
        width: min(92vw, 420px);
        padding: 28px 24px 30px;
    }
}
</style>
