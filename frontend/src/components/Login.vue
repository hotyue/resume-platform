<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { showToast, showLoadingToast, closeToast } from 'vant'
import request from '../api/request.js'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')

// 第三方登录：获取后端配置的前端域名，生成 OAuth 跳转链接
const handleOAuthLogin = (provider) => {
  const redirectPath = window.location.pathname + window.location.search
  window.location.href = `/api/v1/auth/oauth/${provider}/authorize?redirect=${encodeURIComponent(redirectPath)}`
}

const doLogin = async () => {
  if (!username.value || !password.value) {
    showToast('请输入用户名和密码')
    return
  }
  showLoadingToast({ message: '登录中...', forbidClick: true })
  try {
    const res = await request.post('/auth/login', {
      username: username.value,
      password: password.value,
    })
    closeToast()
    const { access_token: token, user } = res.data
    auth.setAuth(token, user)
    showToast('登录成功')
    const redirect = new URLSearchParams(window.location.search).get('redirect')
    router.push(redirect || '/')
  } catch (e) {
    closeToast()
    showToast(e.response?.data?.detail || '登录失败')
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-header">
      <h2>简历模板大全</h2>
      <p>登录后浏览海量简历模板</p>
    </div>

    <van-form @submit="doLogin" class="auth-form">
      <van-cell-group inset>
        <van-field
          v-model="username"
          label="用户名"
          placeholder="输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        />
        <van-field
          v-model="password"
          type="password"
          label="密码"
          placeholder="输入密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        />
      </van-cell-group>

      <div class="auth-action">
        <van-button round block type="primary" native-type="submit">
          登录
        </van-button>
      </div>
    </van-form>

    <!-- 第三方登录 -->
    <div class="oauth-section">
      <div class="divider">
        <span>其他登录方式</span>
      </div>
      <div class="oauth-buttons">
        <van-button round plain type="success" class="oauth-btn" @click="handleOAuthLogin('wechat')">
          <span class="oauth-icon">💬</span> 微信登录
        </van-button>
        <van-button round plain type="primary" class="oauth-btn" @click="handleOAuthLogin('alipay')">
          <span class="oauth-icon">🔵</span> 支付宝登录
        </van-button>
      </div>
      <p class="oauth-hint">第三方登录功能开发中，敬请期待</p>
    </div>

    <div class="auth-footer">
      还没有账号？<router-link to="/register">立即注册</router-link>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  background: #f7f8fa;
  display: flex;
  flex-direction: column;
  padding: 60px 20px 20px;
}
.auth-header { text-align: center; margin-bottom: 30px; }
.auth-header h2 { font-size: 24px; color: #1989fa; margin: 0 0 8px; }
.auth-header p { font-size: 14px; color: #969799; margin: 0; }
.auth-form { margin-bottom: 20px; }
.auth-action { padding: 30px 16px 0; }
.auth-footer { text-align: center; font-size: 14px; color: #646566; margin-top: 20px; }
.auth-footer a { color: #1989fa; }
.oauth-hint { margin-top: 30px; text-align: center; font-size: 12px; color: #c8c9cc; }

/* 第三方登录 */
.oauth-section { margin: 20px 0; }
.divider { display: flex; align-items: center; margin: 20px 0; color: #c8c9cc; font-size: 12px; }
.divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: #ebedf0; }
.divider span { padding: 0 12px; }
.oauth-buttons { display: flex; gap: 12px; justify-content: center; }
.oauth-btn { flex: 1; height: 44px; font-size: 14px; }
.oauth-icon { margin-right: 4px; }
.oauth-hint { text-align: center; font-size: 12px; color: #c8c9cc; margin-top: 8px; }
</style>