<script setup>
import { ref, computed } from 'vue'
import ResumeList from './components/ResumeList.vue'
import CrowdHall from './components/CrowdHall.vue'
import CreatorCenter from './components/CreatorCenter.vue'
import AdminPanel from './components/AdminPanel.vue'
import UserCenter from './components/UserCenter.vue'
import LoginPage from './components/Login.vue'
import RegisterPage from './components/Register.vue'

// 认证状态
const token = ref(localStorage.getItem('token') || '')
const currentUser = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const showLogin = ref(!token.value)
const showRegister = ref(false)

const isLoggedIn = computed(() => !!token.value)
const isAdmin = computed(() => currentUser.value?.role === 'admin')

const activeTab = ref(0)

const onLoginSuccess = (user) => {
  token.value = localStorage.getItem('token') || ''
  currentUser.value = user
  showLogin.value = false
  showRegister.value = false
}

const onRegisterSuccess = (user) => {
  if (user) {
    token.value = localStorage.getItem('token') || ''
    currentUser.value = user
    showLogin.value = false
    showRegister.value = false
  } else {
    // 点击"返回登录"
    showLogin.value = true
    showRegister.value = false
  }
}

const goToRegister = () => {
  showLogin.value = false
  showRegister.value = true
}

const goToLogin = () => {
  showLogin.value = true
  showRegister.value = false
}

const doLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  token.value = ''
  currentUser.value = null
  showLogin.value = true
  window.location.reload()
}
</script>

<template>
  <van-config-provider theme="light">
    <!-- 未登录：登录/注册页 -->
    <template v-if="!isLoggedIn">
      <LoginPage v-if="showLogin" @login-success="onLoginSuccess" @go-register="goToRegister" />
      <RegisterPage v-else @register-success="onRegisterSuccess" @go-login="goToLogin" />

      <!-- 登录页中的"立即注册"链接 -->
      <div v-if="showLogin" class="auth-footer-link">
        还没有账号？<a href="#" @click.prevent="goToRegister">立即注册</a>
      </div>
    </template>

    <!-- 已登录：主界面 -->
    <template v-else>
      <van-nav-bar
        :title="isAdmin ? '后台管理' : '简历模板大全'"
        fixed
        placeholder
        safe-area-inset-top
      >
        <template #right>
          <van-icon name="logout" @click="doLogout" class="logout-icon" />
        </template>
      </van-nav-bar>

      <main class="main-content">
        <ResumeList v-if="activeTab === 0" />
        <CrowdHall v-else-if="activeTab === 1" />
        <CreatorCenter v-else-if="activeTab === 2" />
        <AdminPanel v-if="activeTab === 3 && isAdmin" />
        <UserCenter v-else-if="activeTab === 4" />
      </main>

      <van-tabbar v-model="activeTab" safe-area-inset-bottom>
        <van-tabbar-item icon="home-o">模板商城</van-tabbar-item>
        <van-tabbar-item icon="friends-o">众包大厅</van-tabbar-item>
        <van-tabbar-item icon="gem-o">制作者中心</van-tabbar-item>
        <van-tabbar-item v-if="isAdmin" icon="manager-o">管理后台</van-tabbar-item>
        <van-tabbar-item icon="user-o">我的</van-tabbar-item>
      </van-tabbar>
    </template>
  </van-config-provider>
</template>

<style>
body {
  margin: 0;
  background-color: #f7f8fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Segoe UI, Arial, Roboto, sans-serif;
}
.main-content {
  padding-bottom: 50px;
  min-height: calc(100vh - 46px - 50px);
}
.logout-icon {
  font-size: 20px;
  padding: 0 8px;
}
</style>