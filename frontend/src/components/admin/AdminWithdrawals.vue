<script setup>
import { ref, onMounted, watch } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../../api/request'

const withdrawals = ref([])
const withLoading = ref(true)
const withActiveTab = ref(0)
const withTabs = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' }
]

const showWithDialog = ref(false)
const withRemark = ref('')
const withTransferProof = ref('')
const currentWithdraw = ref(null)
let _withStatus = 'approved'

const withStatusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'default'
}

async function fetchWithdrawals(status = '') {
  try {
    withLoading.value = true
    const res = await request.get('/admin/withdrawals', { params: { status } })
    withdrawals.value = res.data?.withdrawals || []
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    withLoading.value = false
  }
}

function openWithReview(w, status) {
  currentWithdraw.value = w
  withRemark.value = status === 'approved' ? '审核通过' : '审核拒绝'
  withTransferProof.value = ''
  showWithDialog.value = true
  _withStatus = status
}

async function handleWithReview() {
  try {
    await request.post('/admin/withdrawals/review', {
      request_id: currentWithdraw.value.id,
      status: _withStatus,
      remark: withRemark.value,
      transfer_proof: _withStatus === 'approved' ? (withTransferProof.value || null) : null
    })
    showSuccessToast('审核完成')
    showWithDialog.value = false
    await fetchWithdrawals(withTabs[withActiveTab.value].key)
  } catch (e) {
    showToast(e.response?.data?.detail || '操作失败')
  }
}

defineExpose({ fetchWithdrawals, withActiveTab })

onMounted(() => fetchWithdrawals())
watch(withActiveTab, (idx) => fetchWithdrawals(withTabs[idx].key))
</script>

<template>
  <div class="admin-sub">
    <van-tabs v-model:active="withActiveTab" :swipeable="false" color="#1989fa">
      <van-tab v-for="t in withTabs" :key="t.key" :title="t.label" />
    </van-tabs>
    <div v-if="withLoading" class="loading">加载中...</div>
    <div v-else-if="withdrawals.length === 0" class="empty">暂无提现记录</div>
    <div v-else class="with-list">
      <div v-for="w in withdrawals" :key="w.id" class="with-card">
        <div class="with-header">
          <span class="with-user">{{ w.username }}</span>
          <van-tag round :type="withStatusType(w.status)">{{ w.status }}</van-tag>
        </div>
        <div class="with-amount">¥{{ w.amount?.toFixed(2) }}</div>
        <div class="with-info">收款类型: {{ w.account_type || '未指定' }}</div>
        <div class="with-info">收款信息: {{ w.payment_info }}</div>
        <div v-if="w.transfer_proof" class="with-remark">凭证: {{ w.transfer_proof }}</div>
        <div v-if="w.admin_remark" class="with-remark">备注: {{ w.admin_remark }}</div>
        <div class="with-time">{{ w.created_at }}</div>
        <div v-if="w.reviewed_at" class="with-time">审核时间: {{ w.reviewed_at }}</div>
        <div v-if="w.status === 'pending'" class="with-actions">
          <van-button type="success" size="small" round @click="openWithReview(w, 'approved')">通过</van-button>
          <van-button type="danger" size="small" round plain @click="openWithReview(w, 'rejected')">拒绝</van-button>
        </div>
      </div>
    </div>

    <van-dialog v-model:show="showWithDialog" :title="_withStatus === 'approved' ? '通过提现' : '拒绝提现'" show-cancel-button @confirm="handleWithReview">
      <div style="padding: 15px;">
        <van-field v-model="withRemark" label="备注" placeholder="审核备注" />
        <van-field v-if="_withStatus === 'approved'" v-model="withTransferProof" label="转账凭证" placeholder="上传转账截图链接" />
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.with-list { padding: 5px 0; }
.with-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.with-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.with-user { font-weight: bold; font-size: 14px; }
.with-amount { font-size: 20px; font-weight: bold; color: #ee0a24; }
.with-info { font-size: 13px; color: #666; margin-top: 6px; }
.with-remark { font-size: 12px; color: #999; margin-top: 4px; font-style: italic; }
.with-time { font-size: 11px; color: #ccc; margin-top: 4px; }
.with-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }
</style>
