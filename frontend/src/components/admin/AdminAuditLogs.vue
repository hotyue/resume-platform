<script setup>
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import request from '../../api/request'

const logs = ref([])
const logLoading = ref(true)
const logPage = ref(1)
const logPageSize = 20
const logTotal = ref(0)
const logSearch = ref('')

const actionLabel = (a) => {
  const map = {
    order_refund: '退款申请', order_cancel: '订单取消', order_accept: '订单验收',
    creator_penalty: '制作者违约', creator_paused: '制作者暂停', creator_resumed: '制作者恢复',
    withdrawal_approved: '提现通过', withdrawal_rejected: '提现拒绝',
    application_approved: '入驻通过', application_rejected: '入驻拒绝',
    commission_settled: '分佣结算', config_updated: '配置修改',
    user_role_change: '角色变更', user_status_change: '状态变更',
    order_claim: '接单', order_delivery: '交付',
  }
  return map[a] || a
}

async function fetchLogs() {
  try {
    logLoading.value = true
    const params = { page: logPage.value, page_size: logPageSize }
    if (logSearch.value) params.order_no = logSearch.value
    const res = await request.get('/admin/audit-logs', { params })
    logs.value = res.data?.logs || []
    logTotal.value = res.data?.total || 0
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    logLoading.value = false
  }
}

defineExpose({ fetchLogs })

onMounted(fetchLogs)
</script>

<template>
  <div class="admin-sub">
    <div class="log-search">
      <van-search v-model="logSearch" placeholder="搜索订单号" @search="() => { logPage = 1; fetchLogs() }" />
    </div>
    <div v-if="logLoading" class="loading">加载中...</div>
    <div v-else-if="logs.length === 0" class="empty">暂无审计日志</div>
    <div v-else class="log-list">
      <div v-for="log in logs" :key="log.id" class="log-card">
        <div class="log-header">
          <span class="log-action">{{ actionLabel(log.action) }}</span>
          <van-tag size="small" round type="primary">用户 {{ log.user_id }}</van-tag>
        </div>
        <div v-if="log.order_no" class="log-info">订单号: {{ log.order_no }}</div>
        <div v-if="log.detail" class="log-detail">{{ log.detail }}</div>
        <div v-if="log.penalty_amount" class="log-penalty">扣款: ¥{{ log.penalty_amount?.toFixed(2) }}</div>
        <div class="log-time">{{ log.created_at }}</div>
      </div>
    </div>
    <div v-if="logTotal > logPageSize" class="pagination">
      <van-pagination
        :page-count="Math.ceil(logTotal / logPageSize)"
        v-model="logPage"
        @change="fetchLogs"
      />
    </div>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.log-list { padding: 5px 0; }
.log-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.log-action { font-weight: bold; font-size: 14px; }
.log-info { font-size: 13px; color: #666; margin-bottom: 3px; }
.log-detail { font-size: 12px; color: #999; margin-top: 4px; }
.log-penalty { font-size: 14px; font-weight: bold; color: #ee0a24; margin-top: 4px; }
.log-time { font-size: 11px; color: #ccc; margin-top: 6px; }
</style>
