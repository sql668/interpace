import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import InterviewRoom from '../views/InterviewRoom.vue'
import NotebookRoom from '../views/NotebookRoom.vue'
import StudyRoom from '../views/StudyRoom.vue'
import { getAccessToken } from '../api/token'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/interview-room'
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
    }
  ]
})

// 全局前置守卫：未登录拦截并记录跳转来源
router.beforeEach((to) => {
  if (to.path === '/login') {
    return true
  }
  const token = getAccessToken()
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
