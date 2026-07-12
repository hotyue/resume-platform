<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import request from '../api/request.js'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const pendingOrders = ref([])
const isCreator = ref(false)
const loadingOrders = ref(false)

const fetchOrders = async () => {
  loadingOrders.value = true
  try {
    const res = await request.get('/creator/orders?tab=pending')
    pendingOrders.value = res.data
  } catch (error) {
    if (error.response?.status === 403) {
      showToast('请先申请成为制作者')
    }
  } finally {
    loadingOrders.value = false
  }
}

const takeOrder = async (order_no) => {
  showConfirmDialog({
    title: '确认接单',
    message: '接单后 24 小时内需完成交付，超时将被重新发布到众包大厅',
  })
    .then(async () => {
      try {
        await request.post('/creator/take', { order_no })
        showSuccessToast('抢单成功！')
        fetchOrders()
      } catch (error) {
        if (error.response?.status === 403) {
          showToast('只有制作者才能抢单')
        } else {
          showToast(error.response?.data?.detail || '抢单失败')
        }
      }
    })
    .catch(() => {})
}

const statusLabel = (s) => {
  const map = {
    awaiting_claim: '待抢单',
    in_progress: '制作中',
    delivered: '待验收',
    accepted: '已验收',
    rejected: '已退回',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[s] || s
}

const statusType = (s) => {
  const map = {
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    rejected: 'danger',
    completed: 'success',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

const formatTime = (ts) => {
  if (!ts) return '-'
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

onMounted(() => {
  isCreator.value = auth.isCreator
  fetchOrders()
  // 每 60 秒刷新订单列表
  setInterval(fetchOrders, 60000)
})
</script>

<template>
  <div class="crowd-hall">
    <!-- 非制作者提示 -->
    <div v-if="!isCreator" class="not-creator">
      <van-empty description="申请加入制作者，即可接单赚取报酬">
        <van-button type="primary" round to="/creator">立即申请</van-button>
      </van-empty>
    </div>

    <div v-else>
      <div v-if="loadingOrders" class="loading">加载中...</div>
      <div v-else-if="pendingOrders.length === 0" class="empty">暂无待接订单</div>
      <div v-else class="order-list">
        <div v-for="o in pendingOrders" :key="o.order_no" class="order-card">
          <div class="oc-header">
            <span class="oc-order-no">ORD-{{ o.order_no ? o.order_no.slice(-8) : '' }}</span>
            <van-tag round :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
          </div>
          <div class="oc-body">
            <div class="oc-row">
              <span class="oc-label">模板名称</span>
              <span class="oc-val">{{ o.template_name }}</span>
            </div>
            <div class="oc-row">
              <span class="oc-label">订单金额</span>
              <span class="oc-val">¥{{ o.order_amount?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="oc-row">
              <span class="oc-label">报酬</span>
              <span class="oc-val oc-commission">¥{{ o.commission_amount?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="oc-row">
              <span class="oc-label">下单用户</span>
              <span class="oc-val">{{ o.user_name || '未知' }}</span>
            </div>
            <div class="oc-row">
              <span class="oc-label">下单日期</span>
              <span class="oc-val">{{ formatTime(o.created_at) }}</span>
            </div>
            <div v-if="o.requirements" class="oc-req">
              <div class="oc-req-label">需求描述</div>
              <div class="oc-req-text">{{ o.requirements }}</div>
            </div>
          </div>
          <van-button type="primary" size="small" round block @click="takeOrder(o.order_no)">
            立即接单
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.crowd-hall { padding-bottom: 20px; background: #f7f8fa; min-height: 100vh; }
.not-creator { padding: 60px 15px; }

.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }

.order-list { padding: 5px 0; }

.order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

.oc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
.oc-order-no { font-size: 13px; color: #999; font-family: monospace; }

.oc-body { margin-bottom: 10px; }
.oc-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
.oc-label { font-size: 13px; color: #999; min-width: 60px; }
.oc-val { font-size: 13px; color: #323233; text-align: right; word-break: break-all; }
.oc-commission { color: #07c160; font-weight: 600; }

.oc-req { margin-top: 8px; padding: 8px 10px; background: #f7f8fa; border-radius: 6px; }
.oc-req-label { font-size: 11px; color: #999; margin-bottom: 4px; }
.oc-req-text { font-size: 12px; color: #666; line-height: 1.5; }
</style>
