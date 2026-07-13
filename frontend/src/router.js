import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('./components/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('./components/Register.vue') },
  { path: '/auth/callback/:provider', name: 'OAuthCallback', component: () => import('./components/OAuthCallback.vue') },
  {
    path: '/',
    name: 'Home',
    component: () => import('./components/ResumeList.vue'),
  },
  {
    path: '/crowd',
    name: 'CrowdHall',
    component: () => import('./components/CrowdHall.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/creator',
    name: 'CreatorCenter',
    component: () => import('./components/CreatorCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'AdminPanel',
    component: () => import('./components/AdminPanel.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/user',
    name: 'UserCenter',
    component: () => import('./components/UserCenter.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')

  // 已登录则跳过登录/注册页
  if ((to.name === 'Login' || to.name === 'Register') && token) {
    return { name: 'Home' }
  }

  // 需要登录的页面
  if (to.matched.some(r => r.meta.requiresAuth || r.meta.requiresAdmin)) {
    if (!token) {
      return { name: 'Login' }
    }
  }

  // 需要管理员权限的页面
  if (to.matched.some(r => r.meta.requiresAdmin)) {
    if (user?.role !== 'admin') {
      return { name: 'Home' }
    }
  }
})

export default router
