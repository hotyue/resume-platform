<script setup>
import { ref, onMounted, watch } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../../api/request'

const refunds = ref([])
const refundLoading = ref(true)
const refundActiveTab = ref(0)
const refundTabs = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' }
]

const showRefundDialog = ref(false)
const refundRemark = ref('')
const currentRefund = ref(null)
let _refundStatus = 'approved'

const refundStatusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'default'
}

async function fetchRefunds(status = '') {
  try {
    refundLoading.value = true
    const res = await request.get('/admin/refunds', { params: { status } })
    refunds.value = res.data?.refunds || []
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    refundLoading.value = false
  }
}

function openRefundReview(r, status) {
  currentRefund.value = r
  refundRemark.value = status === 'approved' ? '审核通过' : '审核拒绝'
  showRefundDialog.value = true
  _refundStatus = status
}

async function handleRefundReview() {
  try {
    await request.post('/admin/refunds/review', {
      refund_id: currentRefund.value.id,
      status: _refundStatus,
      remark: refundRemark.value
    })
    showSuccessToast('审核完成')
    showRefundDialog.value = false
    await fetchRefunds(refundTabs[refundActiveTab.value].key)
  } catch (e) {
    showToast(e.response?.data?.detail || '操作失败')
  }
}

defineExpose({ fetchRefunds, refundActiveTab })

onMounted(() => fetchRefunds())
watch(refundActiveTab, (idx) => fetchRefunds(refundTabs[idx].key))
</script>

<template>
  <div class="admin-sub">
    <van-tabs v-model:active="refundActiveTab" :swipeable="false" color="#1989fa">
      <van-tab v-for="t in refundTabs" :key="t.key" :title="t.label" />
    </van-tabs>
    <div v-if="refundLoading" class="loading">加载中...</div>
    <div v-else-if="refunds.length === 0" class="empty">暂无退款记录</div>
    <div v-else class="refund-list">
      <div v-for="r in refunds" :key="r.id" class="refund-card">
        <div class="refund-header">
          <span class="refund-no">{{ r.order_no }}</span>
          <van-tag round :type="refundStatusType(r.status)">{{ r.status }}</van-tag>
        </div>
        <div class="refund-info">买家: {{ r.buyer }}</div>
        <div class="refund-info">制作者: {{ r.creator }}</div>
        <div class="refund-amount">退款金额: ¥{{ r.refund_amount?.toFixed(2) }}</div>
        <div class="refund-info">制作者扣款: ¥{{ r.creator_deduction?.toFixed(2) }}</div>
        <div class="refund-reason">原因: {{ r.reason }}</div>
        <div v-if="r.admin_remark" class="refund-remark">备注: {{ r.admin_remark }}</div>
        <div class="refund-time">{{ r.created_at }}</div>
        <div v-if="r.status === 'pending'" class="refund-actions">
          <van-button type="success" size="small" round @click="openRefundReview(r, 'approved')">通过</van-button>
          <van-button type="danger" size="small" round plain @click="openRefundReview(r, 'rejected')">拒绝</van-button>
        </div>
      </div>
    </div>

    <van-dialog v-model:show="showRefundDialog" :title="_refundStatus === 'approved' ? '通过退款' : '拒绝退款'" show-cancel-button @confirm="handleRefundReview">
      <div style="padding: 15px;">
        <van-field v-model="refundRemark" label="备注" placeholder="审核备注" />
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.refund-list { padding: 5px 0; }
.refund-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.refund-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.refund-no { font-weight: bold; font-size: 13px; font-family: monospace; }
.refund-info { font-size: 13px; color: #666; margin-bottom: 3px; }
.refund-amount { font-size: 16px; font-weight: bold; color: #ee0a24; margin: 6px 0; }
.refund-reason { font-size: 12px; color: #999; margin-top: 4px; }
.refund-remark { font-size: 12px; color: #666; margin-top: 4px; font-style: italic; }
.refund-time { font-size: 11px; color: #ccc; margin-top: 4px; }
.refund-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }
</style>
