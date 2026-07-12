<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 全局捕获推广码：URL 中有 ?ref= 时存入 localStorage
if (route.query.ref) {
  localStorage.setItem('invite_code', route.query.ref)
}

// 路由变化时也持续捕获
watch(() => route.query.ref, (ref) => {
  if (ref) {
    localStorage.setItem('invite_code', ref)
  }
})

const isLoggedIn = computed(() => auth.isLoggedIn)
const isAdmin = computed(() => auth.isAdmin)
const isCreator = computed(() => auth.isCreator)

// Tab 定义：根据角色动态生成
const tabs = computed(() => [
  { label: '模板商城', icon: 'home-o', path: '/' },
  { label: '众包大厅', icon: 'friends-o', path: '/crowd' },
  ...(isCreator.value ? [{ label: '制作者中心', icon: 'gem-o', path: '/creator' }] : []),
  ...(isAdmin.value ? [{ label: '管理后台', icon: 'manager-o', path: '/admin' }] : []),
  { label: '我的', icon: 'user-o', path: '/user' },
])

// Vant 4 Tabbar 需要 writable ref 配合 v-model
const activeTab = ref(0)

// 路由 → tab 索引映射（单向同步）
watch(() => route.path, (newPath) => {
  const idx = tabs.value.findIndex(t => t.path === newPath)
  if (idx >= 0) {
    activeTab.value = idx
  }
}, { immediate: true })

// Tab 切换时导航
function onTabChange(idx) {
  const tab = tabs.value[idx]
  if (tab && tab.path !== route.path) {
    router.push(tab.path)
  }
}

const doLogout = () => {
  auth.logout()
  router.push('/')
}
</script>

<template>
  <van-config-provider theme="light">
    <!-- 未登录：只展示模板商城 + 登录入口 -->
    <template v-if="!isLoggedIn">
      <van-nav-bar fixed placeholder safe-area-inset-top>
        <template #title>
          <span class="nav-title">简历模板大全</span>
        </template>
        <template #right>
          <router-link to="/login" class="login-link">登录</router-link>
        </template>
      </van-nav-bar>
      <router-view />
    </template>

    <!-- 已登录：完整主界面 -->
    <template v-else>
      <main class="main-content">
        <router-view />
      </main>

      <van-tabbar v-model="activeTab" @change="onTabChange" fixed safe-area-inset-bottom>
        <van-tabbar-item v-for="(tab, idx) in tabs" :key="tab.path" :icon="tab.icon">
          {{ tab.label }}
        </van-tabbar-item>
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
  min-height: calc(100vh - 50px);
}
.nav-title {
  font-size: 17px;
  font-weight: 600;
  color: #323233;
}
.login-link {
  font-size: 14px;
  color: #1989fa;
  text-decoration: none;
  padding: 0 4px;
}

/* 底部 tabbar 固定在底部，z-index 高于所有模板卡片 */
.van-tabbar {
  z-index: 9999 !important;
}
</style>
