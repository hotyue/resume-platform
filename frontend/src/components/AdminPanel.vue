<script setup>
import { ref } from 'vue'
import AdminDashboard from './admin/AdminDashboard.vue'
import AdminApplications from './admin/AdminApplications.vue'
import AdminOrders from './admin/AdminOrders.vue'
import AdminWithdrawals from './admin/AdminWithdrawals.vue'
import AdminRefunds from './admin/AdminRefunds.vue'
import AdminAuditLogs from './admin/AdminAuditLogs.vue'
import AdminSettings from './admin/AdminSettings.vue'
import AdminUsers from './admin/AdminUsers.vue'

const activeTab = ref(0)
const tabs = ['数据看板', '入驻审核', '订单管理', '提现审核', '退款审核', '审计日志', '系统设置', '用户管理']
</script>

<template>
  <div class="admin-panel">
    <van-tabs v-model:active="activeTab" sticky sticky-offset="46" color="#1989fa">
      <van-tab v-for="(t, i) in tabs" :key="i" :title="t" />
    </van-tabs>
    <div class="admin-content">
      <AdminDashboard v-show="activeTab === 0" />
      <AdminApplications v-show="activeTab === 1" />
      <AdminOrders v-show="activeTab === 2" />
      <AdminWithdrawals v-show="activeTab === 3" />
      <AdminRefunds v-show="activeTab === 4" />
      <AdminAuditLogs v-show="activeTab === 5" />
      <AdminSettings v-show="activeTab === 6" />
      <AdminUsers v-show="activeTab === 7" />
    </div>
  </div>
</template>

<style scoped>
.admin-panel { min-height: 100vh; background: #f5f6f7; padding-bottom: 60px; }
.admin-content { padding: 10px; }
</style>
