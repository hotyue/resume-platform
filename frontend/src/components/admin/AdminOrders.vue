<script setup>
import { ref, onMounted, watch } from 'vue'
import { showToast } from 'vant'
import request from '../../api/request'

const orders = ref([])
const orderLoading = ref(true)
const orderActiveTab = ref(0)
const orderTabs = [
  { key: '', label: '全部' },
  { key: 'paid', label: '已支付' },
  { key: 'claimed', label: '已接单' },
  { key: 'in_progress', label: '制作中' },
  { key: 'delivered', label: '已交付' },
  { key: 'accepted', label: '已验收' },
  { key: 'refunded', label: '已退款' },
]

const orderTypeLabel = (t) => (t === 'custom' ? '定制' : '下载')
const orderStatusType = (s) => {
  const map = { paid: 'primary', awaiting_claim: 'warning', claimed: 'primary', in_progress: 'primary', delivered: 'success', accepted: 'success', refunded: 'danger', cancelled: 'default' }
  return map[s] || 'default'
}

async function fetchOrders(status = '') {
  try {
    orderLoading.value = true
    const res = await request.get('/admin/orders', { params: { status } })
    orders.value = res.data?.orders || []
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    orderLoading.value = false
  }
}

defineExpose({ fetchOrders, orderActiveTab })

onMounted(() => fetchOrders())
watch(orderActiveTab, (idx) => fetchOrders(orderTabs[idx].key))
</script>

<template>
  <div class="admin-sub">
    <van-tabs v-model:active="orderActiveTab" :swipeable="false" color="#1989fa">
      <van-tab v-for="t in orderTabs" :key="t.key" :title="t.label" />
    </van-tabs>
    <div v-if="orderLoading" class="loading">加载中...</div>
    <div v-else-if="orders.length === 0" class="empty">暂无订单</div>
    <div v-else class="order-list">
      <div v-for="order in orders" :key="order.id" class="order-card">
        <div class="order-header">
          <span class="order-no">{{ order.order_no }}</span>
          <div class="order-badges">
            <van-tag size="small" round>{{ orderTypeLabel(order.order_type) }}</van-tag>
            <van-tag size="small" round :type="orderStatusType(order.status)">{{ order.status }}</van-tag>
          </div>
        </div>
        <div class="order-info-row">模板: {{ order.template_name || 'N/A' }}</div>
        <div class="order-info-row">分类: {{ order.template_category || 'N/A' }}</div>
        <div class="order-info-row">用户: {{ order.user_name }}</div>
        <div class="order-info-row">金额: ¥{{ order.amount?.toFixed(2) }}</div>
        <div class="order-info-row">制作者ID: {{ order.creator_id || '无' }}</div>
        <div class="order-info-row">推广人ID: {{ order.ref_user_id || '无' }}</div>
        <div class="order-time">{{ order.created_at }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.order-list { padding: 5px 0; }
.order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.order-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.order-no { font-weight: bold; font-size: 13px; font-family: monospace; }
.order-badges { display: flex; gap: 4px; }
.order-info-row { font-size: 13px; color: #666; margin-bottom: 3px; }
.order-time { font-size: 11px; color: #ccc; margin-top: 6px; }
</style>
