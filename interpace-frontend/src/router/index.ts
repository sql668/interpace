import { createRouter, createWebHistory } from 'vue-router'
import { getAccessToken } from '../api/token'

// 路由级懒加载（T10.4）：页面组件改为动态 import，让 Vite 按页拆包。
// 之前是静态 import，所有页面 + 它们各自的重依赖（笔记页的 wangEditor、
// 代码高亮用的 prismjs 等）都会被打进首屏那一个 2MB 的 chunk 里。
const LoginView = () => import('../views/LoginView.vue')
const HomeView = () => import('../views/HomeView.vue')
const InterviewRoom = () => import('../views/InterviewRoom.vue')
const NotebookRoom = () => import('../views/NotebookRoom.vue')
const ProfileView = () => import('../views/ProfileView.vue')
const StudyRoom = () => import('../views/StudyRoom.vue')

const router = createRouter({
  history: createWebHistory(),
  // 首页有页内锚点导航（功能 / 记忆 / 架构 / 演示环境）。
  // 不配这个的话，点锚点链接浏览器不会滚动——Vue Router 会把带 hash 的跳转接管掉。
  // 顶部留 88px 偏移，避免目标标题被 sticky 顶栏盖住。
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    if (to.hash) {
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      return { el: to.hash, top: 88, behavior: reduceMotion ? 'auto' : 'smooth' }
    }
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      // 首页是公开的介绍页，不再直接跳到面试间——
      // 没登录的人先看到"这是什么、能做什么"，再决定要不要进来。
      component: HomeView
    },
    {
      path: '/study-room',
      component: StudyRoom
    },
    {
      path: '/login',
      component: LoginView
    },
    {
      path: '/interview-room',
      component: InterviewRoom
    },
    {
      path: '/notebook',
      component: NotebookRoom
    },
    {
      path: '/profile',
      component: ProfileView
    }
  ]
})

// 免登录白名单：首页与登录页任何人都能看。
// 白名单做成一个集合而不是 if 链，是为了以后加"关于/文档"这类页面时不用改守卫逻辑。
const PUBLIC_PATHS = new Set(['/', '/login'])

// 全局前置守卫：未登录拦截并记录跳转来源
router.beforeEach((to) => {
  if (PUBLIC_PATHS.has(to.path)) {
    return true
  }
  const token = getAccessToken()
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
