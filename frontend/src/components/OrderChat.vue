<template>
  <div class="chat-page">
    <!-- 顶部栏 -->
    <van-nav-bar :title="orderNo" left-arrow @click-left="goBack" />

    <!-- 消息列表 -->
    <div class="messages-container" ref="msgContainerRef">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="messages.length === 0" class="empty">暂无聊天记录</div>
      <div v-else class="messages-list">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :data-msg-id="msg.id"
          class="message-wrapper"
          :class="[
            msg.sender_id === myUserId ? 'message-self' : 'message-other',
            { 'message-unread': !msg.is_read && msg.sender_id !== myUserId }
          ]"
        >
          <div class="message-bubble">
            <!-- 系统消息 -->
            <div v-if="msg.msg_type === 'system'" class="system-msg">
              {{ msg.content }}
            </div>

            <!-- 文本消息 -->
            <div v-else-if="msg.msg_type === 'text'" class="text-msg">
              {{ msg.content }}
            </div>

            <!-- 图片消息 -->
            <div v-else-if="msg.msg_type === 'image'" class="image-msg">
              <van-image
                :src="fullUrl(msg.attachment_url)"
                width="200"
                height="200"
                fit="cover"
                radius="8"
                @click="previewImage(msg.attachment_url)"
              />
              <div v-if="msg.content && msg.content !== '(文件)'" class="msg-text">
                {{ msg.content }}
              </div>
            </div>

            <!-- 文件消息 -->
            <div v-else-if="msg.msg_type === 'file'" class="file-msg">
              <a :href="fullUrl(msg.attachment_url)" download>
                <van-icon name="download-o" size="24" />
                <span class="file-name">{{ extractFileName(msg.attachment_url) }}</span>
              </a>
              <div v-if="msg.content && msg.content !== '(文件)'" class="msg-text">
                {{ msg.content }}
              </div>
            </div>

            <!-- 时间戳 -->
            <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <!-- 图片预览 -->
      <div v-if="previewImageUrls.length > 0" class="preview-area">
        <van-image
          v-for="(url, idx) in previewImageUrls"
          :key="idx"
          :src="url"
          width="60"
          height="60"
          fit="cover"
          radius="4"
        >
          <template #right-icon>
            <van-icon name="cross2" @click="removeImage(idx)" />
          </template>
        </van-image>
      </div>

      <div class="input-row">
        <van-field
          v-model="inputText"
          type="textarea"
          placeholder="输入消息..."
          rows="2"
          autosize
          @keyup.enter.prevent="handleSend"
        />
        <div class="action-buttons">
          <!-- 图片选择 -->
          <van-button icon="photo-o" size="small" @click="triggerImageUpload" round />
          <!-- 文件选择 -->
          <van-button icon="down" size="small" @click="triggerFileUpload" round />
          <!-- 发送 -->
          <van-button type="primary" size="small" @click="handleSend" round>发送</van-button>
        </div>
      </div>
    </div>

    <!-- 隐藏的文件输入 -->
    <input
      ref="imageInputRef"
      type="file"
      accept="image/jpeg,image/jpg,image/png"
      style="display: none"
      @change="handleImageSelect"
    />
    <input
      ref="fileInputRef"
      type="file"
      accept=".txt,.text,text/plain"
      style="display: none"
      @change="handleFileSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../api/request.js'

const route = useRoute()
const router = useRouter()

const orderId = computed(() => {
  const raw = route.params.order_id
  return raw ? parseInt(raw) : NaN
})
const orderNo = ref('')
const myUserId = ref(null)
const messages = ref([])
const inputText = ref('')
const loading = ref(true)
const ws = ref(null)
const msgContainerRef = ref(null)
const imageInputRef = ref(null)
const fileInputRef = ref(null)
const previewImageUrls = ref([])
const pendingAttachments = ref([])
const reconnectAttempts = ref(0)
const MAX_RECONNECT = 5
const unmounted = ref(false)

// WebSocket URL
const wsUrl = computed(() => {
  const id = orderId.value
  if (isNaN(id) || id <= 0) {
    return null
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const token = localStorage.getItem('token')
  return `${protocol}//${host}/ws/orders/${id}/chat?token=${token}`
})

// 获取完整 URL
const fullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `/api/v1${url}`
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 提取文件名
const extractFileName = (url) => {
  if (!url) return '文件'
  return url.split('/').pop() || '文件'
}

// 图片预览
const previewImage = (url) => {
  const { showImagePreview } = require('vant')
  showImagePreview([fullUrl(url)])
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    const el = msgContainerRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

// 滚动到第一条未读消息；全已读则滚动到底部
const scrollToUnread = () => {
  nextTick(() => {
    const container = msgContainerRef.value
    if (!container) return

    // 找第一条未读消息的 DOM 元素
    const unreadMsg = messages.value.find(m => !m.is_read && m.sender_id !== myUserId.value)
    if (unreadMsg) {
      const el = container.querySelector(`[data-msg-id="${unreadMsg.id}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        return
      }
    }
    // 全已读或没找到 → 滚动到底部
    scrollToBottom()
  })
}

// 标记所有消息为已读
const markMessagesRead = async () => {
  try {
    await request.patch(`/orders/${orderId.value}/messages/read`)
    // 更新本地状态
    messages.value.forEach(m => {
      if (m.sender_id !== myUserId.value) {
        m.is_read = true
      }
    })
  } catch (e) {
    // 静默失败
  }
}

// 加载历史消息
const loadHistory = async () => {
  try {
    const res = await request.get(`/orders/${orderId.value}/messages?offset=0&limit=100`)
    messages.value = res.data.messages || []
    // 先滚动到未读开头（此时还未标记已读）
    scrollToUnread()
    // 再标记为已读
    await markMessagesRead()
  } catch (e) {
    showToast('加载消息失败')
  } finally {
    loading.value = false
  }
}

// 加载订单信息
const loadOrderInfo = async () => {
  try {
    const res = await request.get(`/orders/by-id/${orderId.value}`)
    orderNo.value = res.data.order_no || `订单 #${orderId.value}`
  } catch (e) {
    orderNo.value = `订单 #${orderId.value}`
  }
}

// 获取当前用户 ID
const loadMyUserId = () => {
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  if (user) {
    myUserId.value = user.id
  }
}

// 连接 WebSocket
const connectWS = () => {
  // 无效订单号，不连接
  if (isNaN(orderId.value) || orderId.value <= 0) {
    return
  }

  if (ws.value) {
    ws.value.close()
  }

  const url = wsUrl.value
  if (!url) {
    return
  }

  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    reconnectAttempts.value = 0
    console.log('WebSocket connected')
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'history') {
        messages.value = data.messages || []
        scrollToUnread()
      } else if (data.type === 'message') {
        // 避免重复添加（自己发送的消息已经通过响应添加了）
        const exists = messages.value.find((m) => m.id === data.id)
        if (!exists) {
          // 收到别人的消息，已在聊天页所以标记为已读
          if (data.sender_id !== myUserId.value) {
            data.is_read = true
          }
          messages.value.push(data)
          scrollToBottom()
        }
      }
    } catch (e) {
      console.error('WS message parse error', e)
    }
  }

  ws.value.onclose = () => {
    console.log('WebSocket disconnected')
    // 组件已卸载，不重连
    if (unmounted.value) {
      return
    }
    // 达到最大重连次数，不再重连
    if (reconnectAttempts.value >= MAX_RECONNECT) {
      console.warn(`WebSocket max reconnect attempts (${MAX_RECONNECT}) reached`)
      return
    }
    // 指数退避重连
    const delay = Math.min(3000 * Math.pow(1.5, reconnectAttempts.value), 15000)
    reconnectAttempts.value++
    console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.value}/${MAX_RECONNECT})...`)
    setTimeout(connectWS, delay)
  }

  ws.value.onerror = (err) => {
    console.error('WebSocket error', err)
  }
}

// 发送消息
const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text && previewImageUrls.value.length === 0 && pendingAttachments.value.length === 0) {
    return
  }

  // 发送文本消息
  if (text) {
    try {
      const formData = new FormData()
      formData.append('content', text)
      formData.append('msg_type', 'text')

      // 如果有待发送的附件，一起发送
      if (pendingAttachments.value.length > 0) {
        pendingAttachments.value.forEach((file) => {
          formData.append('attachment', file)
        })
      }

      const res = await request.post(`/orders/${orderId.value}/messages`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      // 自己发送的消息不重复添加（WebSocket 会推送）
      inputText.value = ''
      previewImageUrls.value = []
      pendingAttachments.value = []
    } catch (e) {
      showToast('发送失败')
    }
  }

  // 如果有图片预览但没文本，单独发送图片
  if (!text && previewImageUrls.value.length > 0) {
    await sendImages()
  }
}

// 发送图片
const sendImages = async () => {
  for (const url of previewImageUrls.value) {
    try {
      const formData = new FormData()
      formData.append('content', '(图片)')
      formData.append('msg_type', 'image')
      // 从 URL 获取文件（这里简化处理，实际应该在 select 时保存文件对象）
      const res = await request.post(`/orders/${orderId.value}/messages`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    } catch (e) {
      showToast('图片发送失败')
    }
  }
  previewImageUrls.value = []
}

// 触发图片选择
const triggerImageUpload = () => {
  imageInputRef.value.click()
}

// 处理图片选择
const handleImageSelect = (e) => {
  const files = Array.from(e.target.files)
  files.forEach((file) => {
    // 预览
    const reader = new FileReader()
    reader.onload = (ev) => {
      previewImageUrls.value.push(ev.target.result)
    }
    reader.readAsDataURL(file)

    // 保存到待发送
    pendingAttachments.value.push(file)
  })
  imageInputRef.value.value = ''
}

// 移除预览图片
const removeImage = (idx) => {
  previewImageUrls.value.splice(idx, 1)
  pendingAttachments.value.splice(idx, 1)
}

// 触发文件选择
const triggerFileUpload = () => {
  fileInputRef.value.click()
}

// 处理文件选择
const handleFileSelect = async (e) => {
  const file = e.target.files[0]
  if (!file) return

  try {
    const formData = new FormData()
    formData.append('content', inputText.value.trim() || '(文件)')
    formData.append('msg_type', 'file')
    formData.append('attachment', file)

    await request.post(`/orders/${orderId.value}/messages`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  } catch (e) {
    showToast('文件发送失败')
  }
  fileInputRef.value.value = ''
}

// 返回
const goBack = () => {
  if (ws.value) {
    ws.value.close()
  }
  router.back()
}

// 监听订单 ID 变化，仅在有效时才加载数据
watch(orderId, (newId) => {
  if (isNaN(newId) || newId <= 0) {
    return
  }
  loadOrderInfo()
  loadHistory()
  connectWS()
}, { immediate: true })

onMounted(() => {
  loadMyUserId()
  // 首次加载时，如果订单号无效则返回上一页
  if (isNaN(orderId.value) || orderId.value <= 0) {
    showToast('无效的订单号')
    setTimeout(() => router.back(), 500)
  }
})

onUnmounted(() => {
  unmounted.value = true
  if (ws.value) {
    ws.value.close()
  }
})
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f5f5;
}

.order-no {
  font-size: 12px;
  color: #969799;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-wrapper {
  display: flex;
}

.message-self {
  justify-content: flex-end;
}

.message-other {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message-self .message-bubble {
  background: #1989fa;
  color: #fff;
}

.message-unread .message-bubble {
  border-left: 3px solid #1989fa;
  background: #e8f4fd;
}

.message-unread.message-self .message-bubble {
  border-left: none;
  background: #1989fa;
}

.system-msg {
  text-align: center;
  color: #969799;
  font-size: 12px;
  background: #f7f8fa;
  padding: 4px 12px;
  border-radius: 4px;
}

.text-msg {
  word-break: break-word;
}

.image-msg {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-msg {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-size: 14px;
}

.msg-text {
  font-size: 13px;
  margin-top: 4px;
}

.msg-time {
  font-size: 11px;
  opacity: 0.6;
  margin-top: 4px;
  text-align: right;
}

.input-area {
  border-top: 1px solid #ebedf0;
  background: #fff;
  padding: 8px 12px;
}

.preview-area {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.loading,
.empty {
  text-align: center;
  color: #969799;
  padding: 40px 0;
}
</style>
