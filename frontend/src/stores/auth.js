import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref(localStorage.getItem('token') || '')
  // 清理脏数据（之前的 bug 存入了字符串 "undefined"）
  if (token.value === 'undefined' || token.value === 'null') {
    localStorage.removeItem('token')
    token.value = ''
  }
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isCreator = computed(() => user.value?.role === 'creator')
  const userId = computed(() => user.value?.id)
  const username = computed(() => user.value?.username)
  const authHeader = computed(() =>
    token.value ? `Bearer ${token.value}` : null
  )

  // Actions
  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  function hasPermission(role) {
    return user.value?.role === role
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    isCreator,
    userId,
    username,
    authHeader,
    setAuth,
    logout,
    hasPermission,
  }
})
