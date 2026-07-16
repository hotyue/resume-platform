<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../../api/request'

const config = ref({})
const configLoading = ref(true)

// 编辑弹窗
const showConfigDialog = ref(false)
const editingConfig = ref(null)
const newConfigValue = ref('')

// 配置分组
const amountConfigs = [
  { key: 'download_price', label: '下载价格', icon: 'down' },
  { key: 'custom_price', label: '定制价格', icon: 'edit' },
  { key: 'deposit_amount', label: '保证金金额', icon: 'balance-o' },
  { key: 'auto_accept_hours', label: '自动验收时长', icon: 'clock-o' },
]

const rateConfigs = [
  { key: 'creator_rate', label: '制作者分佣', icon: 'user-circle' },
  { key: 'level1_rate', label: '一级推广分佣', icon: 'friends' },
  { key: 'level2_rate', label: '二级推广分佣', icon: 'friends-o' },
  { key: 'level3_rate', label: '三级推广分佣', icon: 'share' },
]

const otherConfigs = [
  { key: 'delivery_hours', label: '交付周期', icon: 'clock-o' },
  { key: 'penalty_hours', label: '违约金超时', icon: 'warning-o' },
  { key: 'penalty_rate', label: '违约金比例', icon: 'warning' },
  { key: 'penalty_max', label: '违约金上限', icon: 'cash' },
  { key: 'consecutive_fail_limit', label: '连续失败上限', icon: 'closed' },
  { key: 'min_withdraw', label: '最低提现', icon: 'gem' },
  { key: 'deposit_threshold', label: '钱包余额门槛', icon: 'balance-o' },
]

const rateKeys = ['creator_rate', 'level1_rate', 'level2_rate', 'level3_rate']

const configLabel = (key) => {
  const map = {
    download_price: '下载价格（元）',
    custom_price: '定制价格（元）',
    creator_rate: '制作者分佣（%）',
    level1_rate: '一级推广分佣（%）',
    level2_rate: '二级推广分佣（%）',
    level3_rate: '三级推广分佣（%）',
    deposit_amount: '保证金金额（元）',
    auto_accept_hours: '自动验收时长（小时）',
    delivery_hours: '交付周期（小时）',
    penalty_hours: '违约金超时（小时）',
    penalty_rate: '违约金比例（%）',
    penalty_max: '违约金上限（元）',
    consecutive_fail_limit: '连续失败上限（次）',
    min_withdraw: '最低提现（元）',
    deposit_threshold: '钱包余额门槛（元）',
  }
  return map[key] || key
}

const configPlaceholder = (key) => {
  const map = {
    download_price: '如 1.99',
    custom_price: '如 19.99',
    creator_rate: '如 30',
    level1_rate: '如 30',
    level2_rate: '如 10',
    level3_rate: '如 5',
    deposit_amount: '如 20',
    auto_accept_hours: '24-720，如 168',
    delivery_hours: '如 24',
    penalty_hours: '如 8',
    penalty_rate: '如 10',
    penalty_max: '如 50',
    consecutive_fail_limit: '如 3',
    min_withdraw: '如 50',
    deposit_threshold: '如 20',
  }
  return map[key] || ''
}

const formatValue = (key, val) => {
  if (val === null || val === undefined) return '未设置'
  if (rateKeys.includes(key)) return `${(val * 100).toFixed(0)}%`
  if (key.includes('hours')) return `${val} 小时`
  if (key.includes('rate') && !rateKeys.includes(key)) return `${val}%`
  if (key.includes('fail_limit')) return `${val} 次`
  return `¥${Number(val).toFixed(2)}`
}

async function fetchConfig() {
  try {
    configLoading.value = true
    const res = await request.get('/admin/config')
    const data = res.data
    if (typeof data === 'object') {
      Object.keys(data).forEach(key => {
        config.value[key] = parseFloat(data[key])
      })
    }
  } catch (e) {
    showToast(e.response?.data?.detail || '加载配置失败')
  } finally {
    configLoading.value = false
  }
}

function startEditConfig(key) {
  editingConfig.value = key
  const raw = config.value[key]
  newConfigValue.value = rateKeys.includes(key)
    ? (raw * 100).toFixed(0)
    : (raw?.toString() || '0')
  showConfigDialog.value = true
}

function cancelEditConfig() {
  editingConfig.value = null
  newConfigValue.value = ''
  showConfigDialog.value = false
}

async function saveConfig(key) {
  let val = parseFloat(newConfigValue.value)
  if (isNaN(val) || val < 0) {
    showToast('请输入有效数值')
    return
  }
  const storeVal = rateKeys.includes(key) ? val / 100 : val
  try {
    await request.put('/admin/config', { key, value: storeVal })
    showSuccessToast('配置已更新')
    config.value[key] = storeVal
    cancelEditConfig()
  } catch (e) {
    showToast(e.response?.data?.detail || '更新失败')
  }
}

defineExpose({ fetchConfig })

onMounted(() => fetchConfig())
</script>

<template>
  <div class="admin-sub">
    <div v-if="configLoading" class="loading">加载中...</div>
    <div v-else>
      <!-- 金额配置 -->
      <div class="settings-section">
        <div class="settings-title">金额配置</div>
        <div v-for="c in amountConfigs" :key="c.key" class="rate-card" @click="startEditConfig(c.key)">
          <div class="rate-label">{{ c.label }}</div>
          <div class="rate-value">{{ formatValue(c.key, config[c.key]) }} <van-icon name="edit" /></div>
        </div>
      </div>

      <!-- 分佣比例 -->
      <div class="settings-section">
        <div class="settings-title">分佣比例配置</div>
        <div v-for="c in rateConfigs" :key="c.key" class="rate-card" @click="startEditConfig(c.key)">
          <div class="rate-label">{{ c.label }}</div>
          <div class="rate-value">{{ formatValue(c.key, config[c.key]) }} <van-icon name="edit" /></div>
        </div>
      </div>

      <!-- 其他配置 -->
      <div class="settings-section">
        <div class="settings-title">其他配置</div>
        <div v-for="c in otherConfigs" :key="c.key" class="rate-card" @click="startEditConfig(c.key)">
          <div class="rate-label">{{ c.label }}</div>
          <div class="rate-value">{{ formatValue(c.key, config[c.key]) }} <van-icon name="edit" /></div>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <van-dialog
      v-model:show="showConfigDialog"
      title="编辑配置"
      show-cancel-button
      cancel-text="取消"
      confirm-text="保存"
      @confirm="editingConfig && saveConfig(editingConfig)"
      @cancel="cancelEditConfig()"
    >
      <div class="config-edit-form" v-if="editingConfig">
        <div class="config-edit-label">{{ configLabel(editingConfig) }}</div>
        <van-field
          v-model="newConfigValue"
          type="digit"
          :placeholder="configPlaceholder(editingConfig)"
          input-align="center"
          style="font-size: 20px; text-align: center;"
        />
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.settings-section { margin-bottom: 20px; }
.settings-title {
  font-size: 15px;
  font-weight: bold;
  color: #333;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #1989fa;
}
.rate-card {
  background: white;
  border-radius: 8px;
  padding: 12px 15px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  cursor: pointer;
}
.rate-card:active { opacity: 0.8; }
.rate-label { font-size: 14px; color: #333; }
.rate-value {
  font-size: 16px;
  font-weight: bold;
  color: #1989fa;
  display: flex;
  align-items: center;
  gap: 6px;
}
.config-edit-form { padding: 15px 0; }
.config-edit-label { font-size: 14px; font-weight: bold; color: #333; margin-bottom: 10px; text-align: center; }
</style>
