<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showLoadingToast, closeToast } from 'vant'
import axios from 'axios'

const templates = ref([])
const loading = ref(true)
const refreshing = ref(false)

const showCashier = ref(false)
const showCustomForm = ref(false)
const currentOrder = ref(null)
const customReqs = ref('')
const selectedTemplate = ref(null)

// 支付二维码相关
const payQrcode = ref(null)        // base64 data URI
const paymentStatus = ref('pending') // pending / paying / success / fail
const payError = ref('')
const pollTimer = ref(null)

const loadTemplates = async () => {
  try {
    const res = await axios.get('/api/v1/templates?limit=50')
    templates.value = res.data
  } catch (e) {} finally { loading.value = false; refreshing.value = false }
}

const getImageUrl = (relPath) => `/static/${encodeURI(relPath.replace(/\\/g, '/'))}`;

const handleBuy = async (template, type) => {
  if (type === 'custom_service') {
    selectedTemplate.value = template
    showCustomForm.value = true
    return
  }
  submitOrder(template.id, 'download', '')
}

const submitCustomOrder = () => {
  if (!customReqs.value) return showToast('请填写代做需求')
  showCustomForm.value = false
  submitOrder(selectedTemplate.value.id, 'custom_service', customReqs.value)
}

/**
 * 提交订单 -> 弹出收银台 -> 获取支付二维码（带 Mock 降级）
 */
const submitOrder = async (t_id, type, reqs) => {
  // 读取 URL 中的 ref 参数（邀请码）
  const params = new URLSearchParams(window.location.search)
  const refCode = params.get('ref')

  showLoadingToast({ message: '创建订单...', forbidClick: true })
  try {
    const payload = {
      template_id: t_id, order_type: type, custom_requirements: reqs
    }
    // 如果有邀请码，先查询用户 ID
    if (refCode) {
      try {
        const uid = parseInt(refCode.replace('INVITE_', ''), 10)
        if (!isNaN(uid)) payload.ref_user_id = uid
      } catch(e) {}
    }
    const res = await axios.post('/api/v1/orders', payload)
    currentOrder.value = res.data
    paymentStatus.value = 'pending'
    payQrcode.value = null
    payError.value = ''
    showCashier.value = true
    // 关闭 loading 后自动获取二维码
    closeToast()
    await fetchQrcode()
  } catch (e) {
    closeToast()
    showToast('创建订单失败')
  }
}

/**
 * 调用 PayJS 获取二维码；如果 PayJS 未配置，显示 Mock 支付按钮
 */
const fetchQrcode = async () => {
  if (!currentOrder.value?.order_no) return
  showLoadingToast({ message: '获取支付二维码...', forbidClick: true })
  try {
    const res = await axios.post('/api/v1/payments/payjs-qrcode', {
      order_no: currentOrder.value.order_no
    })
    if (res.data.success && res.data.qrcode) {
      payQrcode.value = res.data.qrcode
      paymentStatus.value = 'paying'
      // 开始轮询支付状态
      startPolling()
    } else {
      // PayJS 未配置或失败 -> 降级为 Mock
      payQrcode.value = null
      paymentStatus.value = 'pending'
      payError.value = res.data.message || '支付服务暂不可用'
    }
  } catch (e) {
    // 接口不存在或出错 -> 降级 Mock
    payQrcode.value = null
    paymentStatus.value = 'pending'
    payError.value = '支付服务暂不可用'
  } finally {
    closeToast()
  }
}

/**
 * 轮询订单状态（每 3 秒）
 */
const startPolling = () => {
  stopPolling()
  pollTimer.value = setInterval(async () => {
    try {
      const res = await axios.get(`/api/v1/orders/status/${currentOrder.value.order_no}`)
      if (res.data.status === 'paid') {
        stopPolling()
        paymentStatus.value = 'success'
        showToast({ type: 'success', message: '支付成功！' })
        showCashier.value = false
        // 支付成功 -> 触发下载
        window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
      }
    } catch (e) {
      // 轮询失败静默忽略
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// Mock 支付（降级方案）
const executeMockPay = async () => {
  showLoadingToast({ message: '支付中...', forbidClick: true })
  try {
    await axios.post('/api/v1/payments/mock-callback', { order_no: currentOrder.value.order_no })
    showCashier.value = false
    showToast({ type: 'success', message: '支付成功，开始下载' })
    window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
  } catch (e) {
    showToast('支付失败')
  } finally { closeToast() }
}

// 组件卸载时清理定时器
onMounted(() => loadTemplates())
</script>

<template>
  <div class="resume-list">
    <van-pull-refresh v-model="refreshing" @refresh="loadTemplates">
      <van-grid :column-num="2" :gutter="10">
        <van-grid-item v-for="item in templates" :key="item.id">
          <div class="template-card">
            <div class="image-wrapper">
               <img :src="getImageUrl(item.jpg_path)" class="cover-img" loading="lazy" />
            </div>
            <div class="info">
              <div class="title van-ellipsis">{{ item.category }}-{{ item.name }}</div>
              <div class="action-bar">
                <span class="price">¥{{ item.price }}</span>
                <van-button type="primary" size="mini" plain @click="handleBuy(item, 'download')">下载</van-button>
              </div>
              <van-button type="warning" size="mini" block plain style="margin-top:5px" @click="handleBuy(item, 'custom_service')">代做 (¥19.99)</van-button>
            </div>
          </div>
        </van-grid-item>
      </van-grid>
    </van-pull-refresh>

    <van-dialog v-model:show="showCustomForm" title="填写代做需求" show-cancel-button @confirm="submitCustomOrder">
      <van-field v-model="customReqs" type="textarea" rows="3" placeholder="请填写您的学校、专业、求职意向及内容重点..." />
    </van-dialog>

    <van-popup v-model:show="showCashier" round position="bottom" :style="{ height: '45%' }" @closed="stopPolling">
      <div class="cashier-panel">
        <h3 class="panel-title">{{ currentOrder?.type === 'custom_service' ? '定制代做服务' : '模板自助下载' }}</h3>
        <div class="price-display">¥ {{ currentOrder?.amount || '0.00' }}</div>

        <!-- PayJS 二维码支付 -->
        <div v-if="paymentStatus === 'paying' && payQrcode" class="qrcode-section">
          <img :src="payQrcode" class="qrcode-img" />
          <p class="qrcode-tip">微信扫码支付 ¥{{ currentOrder?.amount }}</p>
        </div>

        <!-- 等待支付 -->
        <div v-if="paymentStatus === 'paying'" class="qrcode-tip-loading">
          <van-loading type="spinner" size="16" /> 等待扫码支付...
        </div>

        <!-- PayJS 不可用 -> 降级 Mock -->
        <div v-if="paymentStatus === 'pending'" class="pay-actions">
          <p v-if="payError" class="pay-error-tip">{{ payError }}</p>
          <van-button type="success" block round @click="executeMockPay">
            (测试) 模拟支付 ¥{{ currentOrder?.amount }}
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.resume-list { padding: 10px; min-height: calc(100vh - 96px); }
.template-card { width: 100%; border-radius: 8px; overflow: hidden; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.image-wrapper { width: 100%; aspect-ratio: 210 / 297; overflow: hidden; display: flex; justify-content: center; align-items: center; }
.cover-img { width: 100%; height: 100%; object-fit: cover; }
.info { padding: 10px; }
.title { font-size: 13px; color: #323233; margin-bottom: 8px; font-weight: 500; }
.action-bar { display: flex; justify-content: space-between; align-items: center; }
.price { color: #ee0a24; font-size: 16px; font-weight: bold; }
.cashier-panel { padding: 20px; text-align: center; }
.panel-title { margin: 0; color: #323233; font-size: 16px; font-weight: normal; }
.price-display { font-size: 36px; font-weight: bold; color: #ee0a24; margin: 15px 0 25px; }
.pay-actions { padding: 0 15px; }
.pay-error-tip { font-size: 12px; color: #999; margin-bottom: 10px; }

.qrcode-section { margin: 10px 0; }
.qrcode-img { width: 180px; height: 180px; display: block; margin: 0 auto; }
.qrcode-tip { font-size: 14px; color: #666; margin-top: 8px; }
.qrcode-tip-loading { font-size: 13px; color: #999; margin-top: 5px; display: flex; align-items: center; justify-content: center; gap: 6px; }
</style>