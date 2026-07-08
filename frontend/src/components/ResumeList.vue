<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showLoadingToast, closeToast } from 'vant'
import axios from 'axios'

const templates = ref([])
const loading = ref(true)
const refreshing = ref(false)

// 支付弹窗状态
const showCashier = ref(false)
const currentOrder = ref(null)

const loadTemplates = async () => {
  try {
    const res = await axios.get('/api/v1/templates?limit=50')
    templates.value = res.data
  } catch (error) {
    showToast("加载模板失败")
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const getImageUrl = (relPath) => {
  if (!relPath) return '';
  return `/static/${encodeURI(relPath.replace(/\\/g, '/'))}`;
}

// 1. 点击下载 -> 创建订单并唤起收银台
const handleBuy = async (template) => {
  showLoadingToast({ message: '创建订单中...', forbidClick: true })
  try {
    // 假设链接里带了 ref_user_id 参数，这里先写死 null 或测试 ID
    const res = await axios.post('/api/v1/orders', {
      template_id: template.id,
      ref_user_id: null // 待接入URL参数读取
    })
    currentOrder.value = res.data
    showCashier.value = true
  } catch (error) {
    showToast('创建订单失败')
  } finally {
    closeToast()
  }
}

// 2. 点击模拟支付 -> 触发支付回调
const executeMockPay = async () => {
  showLoadingToast({ message: '支付处理中...', forbidClick: true })
  try {
    await axios.post('/api/v1/payments/mock-callback', {
      order_no: currentOrder.value.order_no
    })
    showToast({ type: 'success', message: '支付成功，开始下载！' })
    showCashier.value = false
    
    // 3. 触发真实文件下载
    window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
    
  } catch (error) {
    showToast('支付失败')
  } finally {
    closeToast()
  }
}

onMounted(() => loadTemplates())
</script>

<template>
  <div class="resume-list">
    <van-pull-refresh v-model="refreshing" @refresh="loadTemplates">
      <div v-if="loading && !refreshing" class="loading-state">加载中...</div>
      
      <van-grid :column-num="2" :gutter="10" v-else>
        <van-grid-item v-for="item in templates" :key="item.id">
          <div class="template-card">
            <div class="image-wrapper">
               <img :src="getImageUrl(item.jpg_path)" :alt="item.name" class="cover-img" loading="lazy" />
            </div>
            
            <div class="info">
              <div class="title van-ellipsis">{{ item.category }} - {{ item.name }}</div>
              <div class="action-bar">
                <span class="price">¥{{ item.price }}</span>
                <van-button type="primary" size="mini" plain round @click="handleBuy(item)">获取</van-button>
              </div>
            </div>
          </div>
        </van-grid-item>
      </van-grid>
    </van-pull-refresh>

    <van-popup v-model:show="showCashier" round position="bottom" :style="{ height: '35%' }">
      <div class="cashier-panel">
        <h3 class="panel-title">确认订单</h3>
        <div class="price-display">¥ {{ currentOrder?.amount || '0.00' }}</div>
        <p class="order-no">订单号: {{ currentOrder?.order_no }}</p>
        
        <div class="pay-actions">
          <van-button type="success" block round @click="executeMockPay">
            (测试) 模拟微信支付成功
          </van-button>
          <p class="mock-tips">此为旁路测试接口，直接释放发货权限并模拟分账</p>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.resume-list { padding: 10px; min-height: calc(100vh - 96px); }
.loading-state { text-align: center; padding: 40px; color: #999; }
.template-card {
  width: 100%; border-radius: 8px; overflow: hidden;
  background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.image-wrapper {
  width: 100%; aspect-ratio: 210 / 297; overflow: hidden;
  background-color: #f0f2f5; display: flex; justify-content: center; align-items: center;
}
.cover-img { width: 100%; height: 100%; object-fit: cover; }
.info { padding: 10px; }
.title { font-size: 13px; color: #323233; margin-bottom: 8px; font-weight: 500; }
.action-bar { display: flex; justify-content: space-between; align-items: center; }
.price { color: #ee0a24; font-size: 16px; font-weight: bold; }

/* 收银台样式 */
.cashier-panel { padding: 20px; text-align: center; }
.panel-title { margin: 0; color: #323233; font-size: 16px; font-weight: normal; }
.price-display { font-size: 36px; font-weight: bold; color: #ee0a24; margin: 15px 0 5px; }
.order-no { font-size: 12px; color: #969799; margin-bottom: 30px; }
.pay-actions { padding: 0 15px; }
.mock-tips { font-size: 12px; color: #c8c9cc; margin-top: 15px; }
</style>
