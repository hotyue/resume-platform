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

const submitOrder = async (t_id, type, reqs) => {
  showLoadingToast({ message: '创建订单...', forbidClick: true })
  try {
    const res = await axios.post('/api/v1/orders', {
      template_id: t_id, order_type: type, custom_requirements: reqs
    })
    currentOrder.value = res.data
    showCashier.value = true
  } catch (e) { showToast('创建失败') } finally { closeToast() }
}

const executeMockPay = async () => {
  showLoadingToast({ message: '支付中...', forbidClick: true })
  try {
    await axios.post('/api/v1/payments/mock-callback', { order_no: currentOrder.value.order_no })
    showCashier.value = false
    
    // 核心修复：无论哪种订单类型，付款后立刻下发底稿模板让浏览器直接下载
    showToast({ type: 'success', message: '支付成功，开始下载基础底稿' })
    window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
    
  } catch (e) {
    showToast('支付失败')
  } finally { closeToast() }
}
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
              <van-button type="warning" size="mini" block plain style="margin-top:5px" @click="handleBuy(item, 'custom_service')">代做 (¥9.99)</van-button>
            </div>
          </div>
        </van-grid-item>
      </van-grid>
    </van-pull-refresh>

    <van-dialog v-model:show="showCustomForm" title="填写代做需求" show-cancel-button @confirm="submitCustomOrder">
      <van-field v-model="customReqs" type="textarea" rows="3" placeholder="请填写您的学校、专业、求职意向及内容重点..." />
    </van-dialog>

    <van-popup v-model:show="showCashier" round position="bottom" :style="{ height: '35%' }">
      <div class="cashier-panel">
        <h3 class="panel-title">{{ currentOrder?.type === 'custom_service' ? '定制代做服务' : '模板自助下载' }}</h3>
        <div class="price-display">¥ {{ currentOrder?.amount || '0.00' }}</div>
        <div class="pay-actions">
          <van-button type="success" block round @click="executeMockPay">(测试) 模拟支付</van-button>
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
</style>
