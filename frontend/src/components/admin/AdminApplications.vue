<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import request from '../../api/request'

const applications = ref([])
const appLoading = ref(true)
const appActiveTab = ref(0)
const appPage = ref(1)
const appPageSize = 10
const appTotal = ref(0)
const appTabs = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' }
]

const appStatusLabel = (s) => {
  const map = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }
  return map[s] || s
}

const appStatusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'default'
}

async function fetchApplications(status = 'pending') {
  try {
    appLoading.value = true
    const params = {
      status,
      page: appPage.value,
      page_size: appPageSize
    }
    const res = await request.get('/admin/applications', { params })
    applications.value = res.data?.applications || []
    appTotal.value = res.data?.total || 0
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    appLoading.value = false
  }
}

async function handleAppReview(app, status) {
  try {
    await showConfirmDialog({
      title: '确认操作',
      message: `确定要${status === 'approved' ? '通过' : '拒绝'} ${app.real_name} 的入驻申请吗？`
    })
    await request.post('/admin/applications/review', {
      application_id: app.id,
      status,
      remark: status === 'approved' ? '审核通过' : '审核拒绝'
    })
    showSuccessToast('审核完成')
    await fetchApplications(appTabs[appActiveTab.value].key)
  } catch (e) {
    if (e && e.message === 'cancel') return
    showToast(e.response?.data?.detail || '操作失败')
  }
}

defineExpose({ fetchApplications, appActiveTab })

onMounted(() => fetchApplications('pending'))
</script>

<template>
  <div class="admin-sub">
    <van-tabs v-model:active="appActiveTab" :swipeable="false" color="#1989fa" @change="(index) => { appPage = 1; fetchApplications(appTabs[index].key) }">
      <van-tab v-for="t in appTabs" :key="t.key" :title="t.label">
        <div v-if="appLoading" class="loading">加载中...</div>
        <div v-else-if="applications.length === 0" class="empty">暂无记录</div>
        <div v-else class="app-list">
          <div v-for="app in applications" :key="app.id" class="app-card">
            <div class="app-header">
              <span class="app-name">{{ app.real_name }}</span>
              <van-tag round :type="appStatusType(app.status)">{{ appStatusLabel(app.status) }}</van-tag>
            </div>
            <div class="app-info"><van-icon name="contact" /> {{ app.username }}</div>
            <div class="app-info"><van-icon name="phone-o" /> {{ app.phone }}</div>
            <div class="app-info"><van-icon name="chat-o" /> {{ app.wechat }}</div>
            <div v-if="app.specialty" class="app-tags">
              <van-tag v-for="s in app.specialty.split(',')" :key="s" plain size="small" style="margin-right:4px">{{ s.trim() }}</van-tag>
            </div>
            <div v-if="app.portfolio_desc" class="app-desc">作品: {{ app.portfolio_desc }}</div>
            <div v-if="app.experience" class="app-desc">经验: {{ app.experience }}</div>
            <div v-if="app.review_remark" class="app-remark">备注: {{ app.review_remark }}</div>
            <div class="app-time">申请时间: {{ app.created_at }}</div>
            <div v-if="app.status === 'pending'" class="app-actions">
              <van-button type="success" size="small" round @click="handleAppReview(app, 'approved')">通过</van-button>
              <van-button type="danger" size="small" round plain @click="handleAppReview(app, 'rejected')">拒绝</van-button>
            </div>
          </div>
        </div>
        <div v-if="appTotal > appPageSize" class="pagination">
          <van-pagination
            :page-count="Math.ceil(appTotal / appPageSize)"
            v-model="appPage"
            @change="() => fetchApplications(appTabs[appActiveTab].key)"
          />
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.app-list { padding: 5px 0; }
.app-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.app-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.app-name { font-weight: bold; font-size: 15px; }
.app-info { font-size: 13px; color: #666; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.app-tags { margin: 8px 0; }
.app-desc { font-size: 12px; color: #666; margin-top: 6px; padding: 8px; background: #f7f8fa; border-radius: 6px; }
.app-remark { font-size: 12px; color: #999; margin-top: 6px; font-style: italic; }
.app-time { font-size: 11px; color: #ccc; margin-top: 6px; }
.app-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }
.pagination { text-align: center; padding: 16px 0; }
</style>
