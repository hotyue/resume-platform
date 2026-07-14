<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { Toast, Notify } from 'vant'

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

// ─── 未读消息数 ───
const unreadCount = ref(0)
const unreadOrders = ref([])

// ─── 进行中的订单检查 ───
const hasActiveOrders = ref(false)

async function checkActiveOrders() {
  try {
    const token = localStorage.getItem('token')
    if (!token) return
    const res = await fetch('/api/v1/orders/my/active-check', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (res.ok) {
      const data = await res.json()
      hasActiveOrders.value = data.has_active
    }
  } catch {}
}

// ─── 心跳 WebSocket ───
let heartbeatWS = null
let heartbeatTimer = null
let unreadTimer = null
const HEARTBEAT_INTERVAL = 30000 // 30秒
const UNREAD_POLL_INTERVAL = 15000 // 15秒

function startHeartbeat() {
  if (!auth.isLoggedIn) return
  const token = localStorage.getItem('token')
  if (!token) return

  // 请求浏览器通知权限
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission()
  }

  connectHeartbeat(token)

  // 定时刷新未读数
  if (unreadTimer) clearInterval(unreadTimer)
  unreadTimer = setInterval(pollUnreadCount, UNREAD_POLL_INTERVAL)
  pollUnreadCount()

  // 检查进行中的订单
  checkActiveOrders()
}

function connectHeartbeat(token) {
  if (heartbeatWS) {
    heartbeatWS.close()
  }

  const wsUrl = new URL('/ws/user/heartbeat', window.location.origin)
  wsUrl.searchParams.set('token', token)
  heartbeatWS = new WebSocket(wsUrl)

  heartbeatWS.onopen = () => {
    // 启动心跳
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    heartbeatTimer = setInterval(() => {
      if (heartbeatWS && heartbeatWS.readyState === WebSocket.OPEN) {
        heartbeatWS.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  heartbeatWS.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'chat_notification') {
        handleNotification(data)
      }
    } catch {}
  }

  heartbeatWS.onclose = () => {
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    // 3秒后重连
    setTimeout(() => {
      if (auth.isLoggedIn) {
        const token = localStorage.getItem('token')
        if (token) connectHeartbeat(token)
      }
    }, 3000)
  }

  heartbeatWS.onerror = () => {
    heartbeatWS.close()
  }
}

function handleNotification(data) {
  // 如果已经在该订单聊天页，不弹通知
  if (route.path === `/chat/${data.order_id}`) return

  // 页面内 Toast
  Toast({
    message: `💬 ${data.sender_name || '用户'} 发来新消息`,
    duration: 3000,
    position: 'top',
    onClick: () => {
      router.push(`/chat/${data.order_id}`)
    }
  })

  // 浏览器系统通知
  if ('Notification' in window && Notification.permission === 'granted') {
    const notification = new Notification('新消息', {
      body: `${data.sender_name || '用户'}: ${data.content || '新消息'}`,
      icon: '/favicon.ico',
      tag: `chat-${data.order_id}`
    })
    notification.onclick = () => {
      window.focus()
      router.push(`/chat/${data.order_id}`)
    }
  }

  // 刷新未读数
  pollUnreadCount()
}

async function pollUnreadCount() {
  try {
    const token = localStorage.getItem('token')
    if (!token) return
    const res = await fetch('/api/v1/chat/unread-count', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (res.ok) {
      const data = await res.json()
      unreadCount.value = data.unread_count || 0
      unreadOrders.value = data.unread_orders || []
    }
  } catch {}
}

// 点击角标 → 进入第一个未读订单的聊天页
function onBadgeClick() {
  if (unreadOrders.value.length > 0) {
    router.push(`/chat/${unreadOrders.value[0].order_id}`)
  }
}

// ─── 监听路由变化，进入聊天页时标记已读并刷新未读数 ───
watch(() => route.path, (newPath) => {
  if (newPath.startsWith('/chat/')) {
    // 离开聊天页时刷新未读数
  } else {
    // 进入非聊天页时刷新未读数
    setTimeout(pollUnreadCount, 1000)
  }
})

// ─── 生命周期 ───
onMounted(() => {
  if (auth.isLoggedIn) {
    startHeartbeat()
  }
})

onUnmounted(() => {
  if (heartbeatWS) heartbeatWS.close()
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  if (unreadTimer) clearInterval(unreadTimer)
})

// 监听登录状态变化
watch(() => auth.isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    startHeartbeat()
  } else {
    if (heartbeatWS) heartbeatWS.close()
    if (heartbeatTimer) clearInterval(heartbeatTimer)
    if (unreadTimer) clearInterval(unreadTimer)
    unreadCount.value = 0
    hasActiveOrders.value = false
  }
})

const isLoggedIn = computed(() => auth.isLoggedIn)
const isAdmin = computed(() => auth.isAdmin)
const isCreator = computed(() => auth.isCreator)

// Tab 定义：根据角色动态生成
const tabs = computed(() => {
  const result = [
    { label: '模板商城', icon: 'home-o', path: '/' },
    { label: '众包大厅', icon: 'friends-o', path: '/crowd' },
  ]
  // 我的订单：仅当有进行中的订单时显示
  if (hasActiveOrders.value) {
    result.push({ label: '我的订单', icon: 'bill-o', path: '/my-orders' })
  }
  if (isCreator.value) {
    result.push({ label: '制作者中心', icon: 'gem-o', path: '/creator' })
  }
  if (isAdmin.value) {
    result.push({ label: '管理后台', icon: 'manager-o', path: '/admin' })
  }
  result.push({ label: '我的', icon: 'user-o', path: '/user' })
  return result
})

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
          <template #icon="props">
            <div class="icon-wrapper">
              <van-icon :name="props.active ? tab.icon : tab.icon" />
              <van-badge v-if="tab.path === '/user' && unreadCount > 0" :content="unreadCount > 99 ? '99+' : unreadCount" class="icon-badge" @click.stop="onBadgeClick" />
            </div>
          </template>
          <template #default>
            {{ tab.label }}
          </template>
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

.icon-wrapper {
  position: relative;
  display: inline-block;
}

.icon-badge {
  position: absolute;
  top: -6px;
  right: -10px;
  min-width: 16px;
  height: 16px;
  font-size: 10px;
  line-height: 16px;
  padding: 0 4px;
  z-index: 1;
  cursor: pointer;
}
</style>
