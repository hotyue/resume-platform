<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { showLoadingToast, closeToast, showToast } from 'vant'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  const code = route.query.code
  const state = route.query.state
  const provider = route.params.provider

  if (!code) {
    showToast('授权失败：缺少授权码')
    setTimeout(() => router.push('/login'), 2000)
    return
  }

  showLoadingToast({ message: `正在通过${provider === 'wechat' ? '微信' : '支付宝'}登录...`, forbidClick: true })

  try {
    // OAuth callback 不需要 token，直接调用后端
    const res = await fetch(`/api/v1/auth/oauth/${provider}/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state || '')}`)
    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.detail || '授权失败')
    }

    const { token, user } = data
    auth.setAuth(token, user)
    closeToast()
    showToast('登录成功')

    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    closeToast()
    showToast(e.message || '登录失败')
    setTimeout(() => router.push('/login'), 2000)
  }
})
</script>

<template>
  <div class="oauth-callback">
    <van-loading size="24px" vertical>登录中...</van-loading>
  </div>
</template>

<style scoped>
.oauth-callback {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f7f8fa;
}
</style>
