import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器：自动携带认证 token
request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.authHeader) {
    config.headers.Authorization = auth.authHeader
  }
  return config
})

// 响应拦截器：401 自动跳转登录（带 redirect 参数）
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 只在 token 还在时才处理（排除用户主动退出时飞行中的请求）
      if (localStorage.getItem('token')) {
        const auth = useAuthStore()
        auth.logout()
        if (window.location.pathname !== '/login') {
          const redirect = encodeURIComponent(window.location.pathname)
          window.location.href = `/login?redirect=${redirect}`
        }
      }
    }
    return Promise.reject(error)
  }
)

export default request