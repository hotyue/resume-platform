<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showDialog } from 'vant'
import axios from 'axios'

const userInfo = ref(null)
const loading = ref(true)
const showWithdraw = ref(false)
const withdrawAmount = ref('')
const paymentInfo = ref('')

const fetchUserInfo = async () => {
  try {
    const res = await axios.get('/api/v1/user/profile')
    userInfo.value = res.data
  } catch (error) {
    showToast('获取用户信息失败')
  } finally {
    loading.value = false
  }
}

const copyRefLink = () => {
  navigator.clipboard.writeText(userInfo.value.ref_link)
  showSuccessToast('专属推广链接已复制')
}

const submitWithdraw = async () => {
  if (!withdrawAmount.value || !paymentInfo.value) {
    showToast('请填写完整提现信息')
    return
  }
  try {
    const res = await axios.post('/api/v1/user/withdraw', {
      amount: parseFloat(withdrawAmount.value),
      payment_info: paymentInfo.value
    })
    showSuccessToast(res.data.msg)
    showWithdraw.value = false
    userInfo.value.wallet_balance = res.data.balance // 更新本地余额
    withdrawAmount.value = ''
    paymentInfo.value = ''
  } catch (error) {
    showToast(error.response?.data?.detail || '提现失败')
  }
}

onMounted(() => fetchUserInfo())
</script>

<template>
  <div class="user-center">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="userInfo" class="profile-container">
      
      <div class="wallet-card">
        <div class="user-info">
          <van-image round width="50" height="50" src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg" />
          <div class="details">
            <div class="name">{{ userInfo.username }}</div>
            <van-tag type="primary" round>{{ userInfo.role === 'promoter' ? '推广合伙人' : '普通用户' }}</van-tag>
          </div>
        </div>
        <div class="balance-section">
          <div class="label">可提现佣金 (元)</div>
          <div class="amount">{{ userInfo.wallet_balance.toFixed(2) }}</div>
          <van-button size="small" type="primary" round @click="showWithdraw = true" 
            :disabled="userInfo.wallet_balance < 50">
            立即提现
          </van-button>
          <div class="tips" v-if="userInfo.wallet_balance < 50">满50元可提现</div>
        </div>
      </div>

      <van-cell-group inset class="action-group">
        <van-cell title="我的专属推广链接" icon="share-o" is-link @click="copyRefLink" />
        <van-cell title="推广明细 (开发中)" icon="bill-o" is-link />
        <van-cell title="联系管理员" icon="service-o" is-link />
      </van-cell-group>
    </div>

    <van-dialog v-model:show="showWithdraw" title="佣金提现申请" show-cancel-button @confirm="submitWithdraw">
      <div class="withdraw-form">
        <van-field v-model="withdrawAmount" type="number" label="提现金额" placeholder="请输入提现金额" />
        <van-field v-model="paymentInfo" label="收款账号" placeholder="请输入支付宝账号/微信号" />
        <p class="form-tips">注：管理员将在48小时内人工审核并转账</p>
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.user-center { padding: 15px; background: #f7f8fa; min-height: calc(100vh - 96px); }
.loading { text-align: center; margin-top: 50px; color: #999; }
.wallet-card {
  background: linear-gradient(135deg, #ff6034 0%, #ee0a24 100%);
  border-radius: 12px; padding: 20px; color: white; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(238,10,36,0.3);
}
.user-info { display: flex; align-items: center; margin-bottom: 20px; }
.details { margin-left: 15px; }
.name { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
.balance-section { text-align: center; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); }
.label { font-size: 13px; opacity: 0.9; margin-bottom: 5px; }
.amount { font-size: 36px; font-weight: bold; margin-bottom: 15px; font-family: DIN, sans-serif; }
.tips { font-size: 12px; margin-top: 8px; opacity: 0.8; }
.action-group { margin: 0; }
.withdraw-form { padding: 15px 0; }
.form-tips { font-size: 12px; color: #999; text-align: center; margin-top: 10px; }
</style>
