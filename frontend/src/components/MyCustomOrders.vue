<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import request from '../api/request.js'
import { showToast, showSuccessToast, showDialog, showConfirmDialog, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const auth = useAuthStore()

// =========== 定制订单 ===========
const customOrders = ref([])
const customLoading = ref(false)
const reviewForm = ref({ order_no: '', result: 'accepted', buyer_remark: '' })
const showReviewDialog = ref(false)
const reviewing = ref(false)

// =========== 退款 ===========
const showRefund = ref(false)
const refundReason = ref('')
const refunding = ref(false)
const currentRefundOrder = ref(null)

const fetchCustomOrders = async () => {
  customLoading.value = true
  try {
    const res = await request.get('/orders/my')
    customOrders.value = res.data
  } catch (e) {
    showToast('获取定制订单失败')
  } finally {
    customLoading.value = false
  }
}

const openReview = (order) => {
  reviewForm.value = { order_no: order.order_no, result: 'accepted', buyer_remark: '' }
  showReviewDialog.value = true
}

// 预览交付文件
const previewDelivery = async (order, fileType) => {
  try {
    const url = `/api/v1/orders/${order.order_no}/delivery-url?type=${fileType}`
    const token = localStorage.getItem('token')
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '下载失败')
    }
    const blob = await res.blob()
    const disposition = res.headers.get('content-disposition') || ''
    // 优先用后端返回的文件名（RFC 5987 编码需要解码）
    let filename = `${order.order_no}.${fileType === 'word' ? 'docx' : 'pdf'}`
    const match = disposition.match(/filename\*?=UTF-8''(.+)/)
    if (match) {
      filename = decodeURIComponent(match[1])
    } else {
      const match2 = disposition.match(/filename="?(.+)\"?$/)
      if (match2) filename = match2[1]
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    showToast(e.message || '下载失败')
  }
}

const submitReview = async () => {
  reviewing.value = true
  try {
    await request.post('/orders/review', reviewForm.value)
    showSuccessToast(reviewForm.value.result === 'accepted' ? '验收通过' : '已退回重做')
    showReviewDialog.value = false
    await fetchCustomOrders()
  } catch (e) {
    showToast(e.response?.data?.detail || '操作失败')
  } finally {
    reviewing.value = false
  }
}

const openRefund = (order) => {
  currentRefundOrder.value = order
  refundReason.value = ''
  showRefund.value = true
}

const submitRefund = async () => {
  if (!refundReason.value.trim()) {
    return showToast('请填写退款原因')
  }
  refunding.value = true
  try {
    const res = await request.post('/orders/refund', {
      order_no: currentRefundOrder.value.order_no,
      reason: refundReason.value,
    })
    showSuccessToast('退款申请已提交，等待管理员审核')
    showRefund.value = false
    refundReason.value = ''
    currentRefundOrder.value = null
    await fetchCustomOrders()
  } catch (e) {
    showToast(e.response?.data?.detail || '退款申请失败')
  } finally {
    refunding.value = false
  }
}

const orderStatusLabel = (s) => {
  const map = {
    awaiting_claim: '待抢单',
    in_progress: '制作中',
    delivered: '待验收',
    accepted: '已验收',
    rejected: '已退回',
    completed: '已完成',
    paid: '已支付',
    cancelled: '已取消',
  }
  return map[s] || s
}

const orderStatusType = (s) => {
  const map = {
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    rejected: 'danger',
    completed: 'success',
    paid: 'primary',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

const openChat = (orderId) => {
  router.push(`/chat/${orderId}`)
}

onMounted(() => {
  fetchCustomOrders()
})
</script>

<template>
  <div class="my-custom-orders">
    <div v-if="customLoading" class="loading">加载订单中...</div>
    <div v-else-if="customOrders.length === 0" class="empty-hint">暂无定制订单</div>
    <div v-else class="order-list">
      <div v-for="o in customOrders" :key="o.order_no" class="custom-order-card">
        <div class="co-header">
          <van-tag :type="orderStatusType(o.status)" round size="small">{{ orderStatusLabel(o.status) }}</van-tag>
          <span class="co-no">{{ o.order_no }}</span>
        </div>
        <div class="co-body">
          <p><strong>{{ o.template_name }}</strong></p>
          <p class="co-req">{{ o.custom_requirements || '暂无需求描述' }}</p>
          <p class="co-amount">¥{{ o.amount.toFixed(2) }}</p>
          <p v-if="o.creator_name" class="co-creator" @click="openChat(o.id)">👤 接单人: {{ o.creator_name }}</p>
          <p v-if="o.status === 'delivered'" class="co-frozen">⏳ 等待验收（7天自动通过）</p>
          <!-- 预览交付文件 -->
          <div v-if="['delivered', 'accepted'].includes(o.status)" class="co-preview">
            <van-button size="mini" plain type="primary" @click="previewDelivery(o, 'pdf')">📄 预览PDF</van-button>
            <van-button size="mini" plain type="primary" @click="previewDelivery(o, 'word')">📝 预览Word</van-button>
          </div>
        </div>
        <div class="co-footer">
          <div class="co-actions-row" v-if="o.status === 'delivered'">
            <van-button size="small" round block type="primary" @click="openReview(o)">验收订单</van-button>
            <van-button size="small" round block plain type="danger" @click="openRefund(o)">申请退款</van-button>
          </div>
          <van-button v-if="o.status === 'in_progress'" size="small" round block plain type="danger" @click="openRefund(o)">申请退款</van-button>
          <van-button v-if="o.status === 'accepted'" size="small" round block plain type="success">已验收通过</van-button>
          <van-button v-if="o.status === 'rejected'" size="small" round block plain type="warning">已退回重做</van-button>
          <van-button v-if="o.status === 'refund_requested'" size="small" round block plain type="default">退款审核中</van-button>
        </div>
      </div>
    </div>

    <!-- 验收弹窗 -->
    <van-dialog v-model:show="showReviewDialog" :show-cancel-button="true" @confirm="submitReview" :before-close="() => true" :close-on-click-overlay="false">
      <div class="review-form">
        <van-radio-group v-model="reviewForm.result" direction="horizontal">
          <van-radio name="accepted" icon-size="20px">✅ 验收通过</van-radio>
          <van-radio name="rejected" icon-size="20px">❌ 退回重做</van-radio>
        </van-radio-group>
        <van-field v-model="reviewForm.buyer_remark" rows="2" autosize type="textarea" placeholder="验收备注（可选）" />
      </div>
    </van-dialog>

    <!-- 退款弹窗 -->
    <van-dialog v-model:show="showRefund" title="申请退款" show-cancel-button confirm-button-text="提交申请" @confirm="submitRefund" :before-close="() => true" :close-on-click-overlay="false">
      <div class="refund-form">
        <div class="refund-info" v-if="currentRefundOrder">
          <p>订单号：{{ currentRefundOrder.order_no }}</p>
          <p>订单金额：¥{{ currentRefundOrder.amount?.toFixed(2) }}</p>
          <p class="refund-note">⚠️ 退款金额：¥{{ (currentRefundOrder.amount / 2)?.toFixed(2) }}（平台与创作者各承担50%）</p>
        </div>
        <van-field v-model="refundReason" rows="3" autosize type="textarea" label="退款原因" placeholder="请详细说明退款原因" />
        <p class="form-tips">退款申请提交后需管理员审核，仅可退款一次</p>
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.my-custom-orders { padding: 15px; background: #f7f8fa; min-height: calc(100vh - 96px); }
.loading { text-align: center; margin-top: 50px; color: #999; padding: 30px 0; }
.empty-hint { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }
.order-list { padding-bottom: 20px; }

/* 定制订单 */
.custom-order-card { background: white; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.co-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.co-no { font-size: 11px; color: #999; }
.co-body p { margin: 4px 0; font-size: 13px; }
.co-req { color: #666; font-size: 12px; line-height: 1.4; }
.co-amount { color: #ee0a24; font-weight: bold; font-size: 15px; }
.co-frozen { font-size: 11px; color: #ff976a; margin-top: 6px; padding: 4px 8px; background: #fffbe6; border-radius: 4px; text-align: center; }
.co-creator { color: #1989fa; cursor: pointer; }
.co-preview { display: flex; gap: 8px; margin-top: 8px; }
.co-footer { margin-top: 10px; }
.co-actions-row { display: flex; gap: 8px; margin-bottom: 8px; }

/* 验收弹窗 */
.review-form { padding: 15px 10px; }
.review-form .van-radio-group { margin-bottom: 12px; }
.review-form .van-radio { margin-right: 15px; }
.review-form .van-field { margin-top: 10px; }

/* 退款 */
.refund-form { padding: 15px 0; }
.refund-info { background: #fff7cc; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 13px; }
.refund-info p { margin: 4px 0; }
.refund-note { color: #ee0a24; font-weight: bold; }
.form-tips { font-size: 12px; color: #999; text-align: center; margin-top: 10px; }
</style>
