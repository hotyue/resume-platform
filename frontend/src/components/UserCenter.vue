<script setup>
import { ref, onMounted, computed } from 'vue'
import { showToast, showSuccessToast, showDialog, showLoadingToast, closeToast } from 'vant'
import axios from 'axios'

const activeTab = ref(0)
const userInfo = ref(null)
const loading = ref(true)
const teamData = ref(null)
const teamLoading = ref(false)
const commissionList = ref([])
const commissionLoading = ref(false)
const stats = ref(null)
const statsLoading = ref(false)

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

const fetchTeam = async () => {
  teamLoading.value = true
  try {
    const res = await axios.get('/api/v1/user/team')
    teamData.value = res.data
  } catch (e) {
    showToast('获取团队信息失败')
  } finally {
    teamLoading.value = false
  }
}

const fetchCommissionHistory = async () => {
  commissionLoading.value = true
  try {
    const res = await axios.get('/api/v1/user/commission-history')
    commissionList.value = res.data
  } catch (e) {
    showToast('获取佣金记录失败')
  } finally {
    commissionLoading.value = false
  }
}

const fetchStats = async () => {
  statsLoading.value = true
  try {
    const id = userInfo.value?.id || 2
    const res = await axios.get(`/api/v1/user/stats/${id}`)
    stats.value = res.data
  } catch (e) {
    // ignore
  } finally {
    statsLoading.value = false
  }
}

const onTabChange = (index) => {
  activeTab.value = index
  if (index === 1 && !teamData.value) fetchTeam()
  if (index === 2 && commissionList.value.length === 0) fetchCommissionHistory()
}

const copyInviteLink = () => {
  if (!userInfo.value?.invite_url) return showToast('暂无邀请链接')
  navigator.clipboard.writeText(userInfo.value.invite_url)
  showSuccessToast('邀请链接已复制')
}

const copyInviteCode = () => {
  if (!userInfo.value?.invite_code) return showToast('暂无邀请码')
  navigator.clipboard.writeText(userInfo.value.invite_code)
  showSuccessToast('邀请码已复制')
}

const teamCount = computed(() => {
  if (!teamData.value) return 0
  return (teamData.value.level_1?.length || 0) +
         (teamData.value.level_2?.length || 0) +
         (teamData.value.level_3?.length || 0)
})

const roleLabel = (role) => {
  const map = { promoter: '推广合伙人', creator: '制作者', user: '普通用户' }
  return map[role] || role
}

onMounted(() => {
  fetchUserInfo().then(() => fetchStats())
})
</script>

<template>
  <div class="user-center">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="userInfo">
      <!-- 钱包概览 -->
      <div class="wallet-card">
        <div class="user-info">
          <van-image round width="50" height="50" src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg" />
          <div class="details">
            <div class="name">{{ userInfo.username }}</div>
            <van-tag type="primary" round>{{ roleLabel(userInfo.role) }}</van-tag>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-item">
            <div class="stat-val">{{ userInfo.team_size || 0 }}</div>
            <div class="stat-lbl">团队人数</div>
          </div>
          <div class="stat-item">
            <div class="stat-val">¥{{ userInfo.wallet_balance?.toFixed(2) }}</div>
            <div class="stat-lbl">可提现佣金</div>
          </div>
          <div class="stat-item">
            <div class="stat-val">¥{{ stats?.total_commission?.toFixed(2) || '0.00' }}</div>
            <div class="stat-lbl">累计收益</div>
          </div>
        </div>
        <div class="balance-actions">
          <van-button size="small" type="primary" round @click="showWithdraw = true"
            :disabled="(userInfo.wallet_balance || 0) < 50">
            立即提现
          </van-button>
          <van-button size="small" round plain @click="copyInviteLink">
            复制邀请链接
          </van-button>
        </div>
        <div class="tips" v-if="(userInfo.wallet_balance || 0) < 50">满50元可提现</div>
      </div>

      <!-- 三级分佣说明 -->
      <div class="commission-rules">
        <div class="rule-item" v-for="(r, i) in [
          { level: '一级', rate: '15%', desc: '直接推荐用户下单' },
          { level: '二级', rate: '8%', desc: '下级推荐用户下单' },
          { level: '三级', rate: '5%', desc: '下下级推荐用户下单' },
        ]" :key="i">
          <span class="rule-level">{{ r.level }}</span>
          <span class="rule-rate">{{ r.rate }}</span>
          <span class="rule-desc">{{ r.desc }}</span>
        </div>
      </div>

      <!-- 三 Tab：团队 / 佣金明细 / 邀请 -->
      <van-tabs @change="onTabChange" color="#ee0a24">
        <van-tab title="我的团队">
          <div v-if="teamLoading" class="loading">加载团队信息...</div>
          <div v-else-if="teamData" class="team-tree">
            <div class="team-summary">团队共 <strong>{{ teamCount }}</strong> 人（含直接+间接）</div>

            <!-- 我 -->
            <div class="tree-node level-self">
              <van-icon name="contact" /> {{ teamData.level_0.username }}
              <van-tag size="mini" round>{{ roleLabel(teamData.level_0.role) }}</van-tag>
              <span class="node-balance">¥{{ teamData.level_0.wallet_balance?.toFixed(2) }}</span>
            </div>

            <!-- 一级 -->
            <div v-if="teamData.level_1?.length" class="level-section">
              <div class="level-header"><van-icon name="down" /> 一级成员（直接邀请）</div>
              <div v-for="m in teamData.level_1" :key="m.id" class="tree-node level-1">
                <van-icon name="user" /> {{ m.username }}
                <van-tag size="mini" round>{{ roleLabel(m.role) }}</van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
              </div>
            </div>
            <div v-else class="empty-hint">暂无一级成员</div>

            <!-- 二级 -->
            <div v-if="teamData.level_2?.length" class="level-section">
              <div class="level-header"><van-icon name="down" /> 二级成员（间接邀请）</div>
              <div v-for="m in teamData.level_2" :key="m.id" class="tree-node level-2">
                <van-icon name="user" /> {{ m.username }}
                <van-tag size="mini" round>{{ roleLabel(m.role) }}</van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
              </div>
            </div>

            <!-- 三级 -->
            <div v-if="teamData.level_3?.length" class="level-section">
              <div class="level-header"><van-icon name="down" /> 三级成员</div>
              <div v-for="m in teamData.level_3" :key="m.id" class="tree-node level-3">
                <van-icon name="user" /> {{ m.username }}
                <van-tag size="mini" round>{{ roleLabel(m.role) }}</van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
              </div>
            </div>
          </div>
        </van-tab>

        <van-tab title="佣金明细">
          <div v-if="commissionLoading" class="loading">加载佣金记录...</div>
          <div v-else-if="commissionList.length === 0" class="empty-hint">暂无佣金记录</div>
          <div v-else class="commission-list">
            <div class="list-header">共 {{ commissionList.length }} 条记录</div>
            <div v-for="r in commissionList" :key="r.id" class="commission-item">
              <div class="ci-left">
                <div class="ci-level">
                  <van-tag :type="r.level === 1 ? 'danger' : r.level === 2 ? 'warning' : 'default'" size="mini" round>
                    {{ r.level === 1 ? '一级' : r.level === 2 ? '二级' : '三级' }}
                  </van-tag>
                  <span class="ci-rate">({{ (r.rate * 100).toFixed(0) }}%)</span>
                </div>
                <div class="ci-order">订单：{{ r.order_no }}</div>
              </div>
              <div class="ci-amount">+ ¥{{ r.amount.toFixed(2) }}</div>
            </div>
          </div>
        </van-tab>

        <van-tab title="邀请推广">
          <div class="invite-panel">
            <div class="invite-section">
              <div class="invite-label">你的邀请码</div>
              <div class="invite-code-box" @click="copyInviteCode">
                <span class="code-text">{{ userInfo.invite_code }}</span>
                <van-icon name="copy" />
              </div>
            </div>

            <div class="invite-section">
              <div class="invite-label">邀请链接</div>
              <div class="invite-url-box">
                <div class="url-text van-ellipsis">{{ userInfo.invite_url }}</div>
                <van-button size="mini" type="primary" @click="copyInviteLink">复制</van-button>
              </div>
            </div>

            <div class="invite-instructions">
              <h4>推广规则</h4>
              <ul>
                <li>邀请好友注册，好友下单你获得 <strong>15%</strong> 佣金</li>
                <li>好友邀请的下级下单，你获得 <strong>8%</strong> 佣金</li>
                <li>三级以内间接订单，你获得 <strong>5%</strong> 佣金</li>
                <li>佣金满 50 元可申请提现</li>
              </ul>
            </div>
          </div>
        </van-tab>
      </van-tabs>
    </div>

    <!-- 提现弹窗 -->
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
.loading { text-align: center; margin-top: 50px; color: #999; padding: 30px 0; }
.empty-hint { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }

/* 钱包卡片 */
.wallet-card {
  background: linear-gradient(135deg, #ff6034 0%, #ee0a24 100%);
  border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(238,10,36,0.3);
}
.user-info { display: flex; align-items: center; margin-bottom: 15px; }
.details { margin-left: 15px; }
.name { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
.stats-row { display: flex; justify-content: space-around; text-align: center; margin-bottom: 15px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.2); border-bottom: 1px solid rgba(255,255,255,0.2); }
.stat-val { font-size: 20px; font-weight: bold; font-family: DIN, sans-serif; }
.stat-lbl { font-size: 12px; opacity: 0.85; margin-top: 3px; }
.balance-actions { display: flex; gap: 10px; justify-content: center; margin-bottom: 5px; }
.tips { font-size: 12px; margin-top: 5px; opacity: 0.8; text-align: center; }

/* 分佣比例说明 */
.commission-rules { display: flex; gap: 8px; margin-bottom: 15px; }
.rule-item { flex: 1; background: white; border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.rule-level { display: block; font-size: 12px; color: #999; }
.rule-rate { display: block; font-size: 20px; font-weight: bold; color: #ee0a24; margin: 3px 0; }
.rule-desc { display: block; font-size: 11px; color: #666; }

/* 团队树 */
.team-tree { padding: 5px 0; }
.team-summary { text-align: center; font-size: 13px; color: #666; margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px; }
.tree-node { display: flex; align-items: center; gap: 6px; padding: 10px 12px; margin-bottom: 5px; background: white; border-radius: 8px; font-size: 14px; border-left: 3px solid #ee0a24; }
.level-self { border-left-color: #ee0a24; font-weight: bold; }
.level-1 { border-left-color: #ff976a; margin-left: 15px; }
.level-2 { border-left-color: #ffc8a2; margin-left: 30px; }
.level-3 { border-left-color: #ffe0cc; margin-left: 45px; }
.node-balance { margin-left: auto; font-size: 12px; color: #999; }
.level-section { margin-top: 10px; }
.level-header { font-size: 12px; color: #999; padding: 5px 0; margin-left: 5px; }

/* 佣金明细 */
.commission-list { padding: 5px 0; }
.list-header { font-size: 12px; color: #999; text-align: center; margin-bottom: 10px; }
.commission-item { display: flex; align-items: center; justify-content: space-between; background: white; border-radius: 8px; padding: 12px; margin-bottom: 6px; }
.ci-left { display: flex; flex-direction: column; gap: 4px; }
.ci-level { display: flex; align-items: center; gap: 4px; }
.ci-rate { font-size: 11px; color: #999; }
.ci-order { font-size: 12px; color: #666; }
.ci-amount { font-size: 16px; font-weight: bold; color: #07c160; }

/* 邀请 */
.invite-panel { padding: 10px 0; }
.invite-section { margin-bottom: 15px; }
.invite-label { font-size: 13px; color: #666; margin-bottom: 6px; }
.invite-code-box { display: flex; align-items: center; justify-content: space-between; background: white; border-radius: 8px; padding: 12px 15px; cursor: pointer; }
.code-text { font-size: 20px; font-weight: bold; letter-spacing: 2px; color: #ee0a24; user-select: all; }
.invite-url-box { display: flex; align-items: center; gap: 8px; background: white; border-radius: 8px; padding: 10px 12px; }
.url-text { flex: 1; font-size: 12px; color: #666; }
.invite-instructions { background: white; border-radius: 8px; padding: 15px; margin-top: 10px; }
.invite-instructions h4 { margin: 0 0 10px; font-size: 14px; }
.invite-instructions ul { margin: 0; padding-left: 18px; font-size: 13px; color: #666; line-height: 1.8; }

/* 提现 */
.withdraw-form { padding: 15px 0; }
.form-tips { font-size: 12px; color: #999; text-align: center; margin-top: 10px; }
</style>