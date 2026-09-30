/**
 * 顶部导航标签常量。
 *
 * 学习室 / 面试间 / 笔记本三个页面共用同一份定义。它原来放在
 * `composables/useRoomShell.ts` 里，但那个文件剩余的 mock 会话与 `useRoomShell`
 * 函数早已没有调用方，所以把常量单独拆出来，删掉废弃部分。
 */

export type NavTab = {
  key: string
  label: string
  path: string
}

export const tabs: NavTab[] = [
  { key: 'study-room', label: '学习室', path: '/study-room' },
  { key: 'interview-room', label: '面试间', path: '/interview-room' },
  { key: 'notebook', label: '笔记本', path: '/notebook' },
  // 「我的画像」是记忆可解释的入口：用户能看到系统记住了自己什么，也能删掉记错的
  { key: 'profile', label: '我的画像', path: '/profile' }
]
