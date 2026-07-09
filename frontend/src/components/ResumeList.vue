<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { showToast, showLoadingToast, closeToast } from 'vant'
import request from '../api/request.js'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()

const templates = ref([])
const loading = ref(false)
const refreshing = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)

const showCashier = ref(false)
const showCustomForm = ref(false)
const currentOrder = ref(null)
const customReqs = ref('')
const selectedTemplate = ref(null)

// 支付二维码相关
const payQrcode = ref(null)
const paymentStatus = ref('pending')
const payError = ref('')
const pollTimer = ref(null)

// 分页配置
const PAGE_SIZE = 20
const page = ref(1)

// 分类筛选
const categories = [
  { key: '', label: '全部' },
  { key: '1.中文简历', label: '中文简历' },
  { key: '2.EnglishResume', label: '英文简历' },
  { key: '3.多页简历', label: '多页简历' },
  { key: '4.简历封面', label: '简历封面' },
  { key: '5.简单表格简历', label: '表格简历' },
]
const activeCategory = ref('')
const searchKeyword = ref('')

// ================= 懒加载 (IntersectionObserver) =================
let observer = null

const setupLazyObserver = () => {
  if (observer) observer.disconnect()

  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target
        if (img.dataset.src) {
          img.src = img.dataset.src
          img.removeAttribute('data-src')
        }
        observer.unobserve(img)
      }
    })
  }, {
    rootMargin: '300px', // 提前 300px 开始加载
  })
}

const observeImages = () => {
  nextTick(() => {
    document.querySelectorAll('.cover-img[data-src]').forEach(img => {
      observer.observe(img)
    })
  })
}

// ================= 分页加载 =================
const loadTemplates = async (category = '', append = false) => {
  // 防止重复请求
  if (append && (loadingMore.value || loading.value)) return
  if (!append && loading.value) return

  if (append) loadingMore.value = true
  else loading.value = true

  try {
    const p = append ? page.value : 1
    if (!append) {
      page.value = 1
      templates.value = []
    }

    const params = new URLSearchParams({
      page: String(p),
      page_size: String(PAGE_SIZE),
    })
    if (category) params.set('category', category)
    if (searchKeyword.value) params.set('search', searchKeyword.value)

    const res = await request.get(`/templates?${params.toString()}`)
    // 后端返回 {total, page, page_size, templates: [...]}
    const data = res.data?.templates || res.data?.data || []

    if (append) {
      templates.value = [...templates.value, ...data]
    } else {
      templates.value = data
    }

    hasMore.value = data.length === PAGE_SIZE
    if (append) page.value++

    // 观察新加载的图片
    observeImages()
  } catch (e) {} finally {
    loading.value = false
    refreshing.value = false
    loadingMore.value = false
  }
}

const loadMore = () => {
  if (!hasMore.value || loadingMore.value || loading.value) return
  loadTemplates(activeCategory.value, true)
}

const switchCategory = (key) => {
  activeCategory.value = key
  searchKeyword.value = ''
  loadTemplates(key)
}

const doSearch = () => {
  if (!auth.isLoggedIn) {
    showToast('请先登录后搜索')
    router.push('/login')
    return
  }
  loadTemplates(activeCategory.value)
}

const getImageUrl = (relPath) => `/static/${encodeURI(relPath.replace(/\\/g, '/'))}`

// ================= 滚动监听（分页触发） =================
const handleScroll = () => {
  const scrollTop = window.scrollY || window.pageYOffset
  const windowHeight = window.innerHeight
  const docHeight = document.documentElement.scrollHeight
  // 距离底部 200px 时触发加载
  if (scrollTop + windowHeight >= docHeight - 200) {
    loadMore()
  }
}

// ================= 购买 / 支付 =================
const handleBuy = async (template, type) => {
  if (!auth.isLoggedIn) {
    showToast('请先登录')
    router.push('/login')
    return
  }
  if (type === 'custom_service') {
    selectedTemplate.value = template
    showCustomForm.value = true
    return
  }
  submitOrder(template.id, 'download', '')
}

const submitCustomOrder = () => {
  if (!customReqs.value) return showToast('请填写代做需求')
  showCustomForm.value = false
  submitOrder(selectedTemplate.value.id, 'custom_service', customReqs.value)
}

const submitOrder = async (t_id, type, reqs) => {
  const params = new URLSearchParams(window.location.search)
  const refCode = params.get('ref')

  showLoadingToast({ message: '创建订单...', forbidClick: true })
  try {
    const payload = {
      template_id: t_id, order_type: type, custom_requirements: reqs
    }
    if (refCode) {
      try {
        const uid = parseInt(refCode.replace('INVITE_', ''), 10)
        if (!isNaN(uid)) payload.ref_user_id = uid
      } catch(e) {}
    }
    const res = await request.post('/orders', payload)
    currentOrder.value = res.data
    paymentStatus.value = 'pending'
    payQrcode.value = null
    payError.value = ''
    showCashier.value = true
    closeToast()
    await fetchQrcode()
  } catch (e) {
    closeToast()
    showToast('创建订单失败')
  }
}

const fetchQrcode = async () => {
  if (!currentOrder.value?.order_no) return
  showLoadingToast({ message: '获取支付二维码...', forbidClick: true })
  try {
    const res = await request.post('/payments/payjs-qrcode', {
      order_no: currentOrder.value.order_no
    })
    if (res.data.success && res.data.qrcode) {
      payQrcode.value = res.data.qrcode
      paymentStatus.value = 'paying'
      startPolling()
    } else {
      payQrcode.value = null
      paymentStatus.value = 'pending'
      payError.value = res.data.message || '支付服务暂不可用'
    }
  } catch (e) {
    payQrcode.value = null
    paymentStatus.value = 'pending'
    payError.value = '支付服务暂不可用'
  } finally {
    closeToast()
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer.value = setInterval(async () => {
    try {
      const res = await request.get(`/orders/status/${currentOrder.value.order_no}`)
      if (res.data.status === 'paid') {
        stopPolling()
        paymentStatus.value = 'success'
        showToast({ type: 'success', message: '支付成功！' })
        showCashier.value = false
        window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
      }
    } catch (e) {}
  }, 3000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const executeMockPay = async () => {
  showLoadingToast({ message: '支付中...', forbidClick: true })
  try {
    await request.post('/payments/mock-callback', { order_no: currentOrder.value.order_no })
    showCashier.value = false
    showToast({ type: 'success', message: '支付成功，开始下载' })
    window.location.href = `/api/v1/orders/download/${currentOrder.value.order_no}`
  } catch (e) {
    showToast('支付失败')
  } finally { closeToast() }
}

onMounted(() => {
  loadTemplates()
  setupLazyObserver()
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
  if (observer) observer.disconnect()
  stopPolling()
})
</script>

<template>
  <div class="resume-list">
    <!-- 分类筛选栏 -->
    <div class="category-bar">
      <div class="category-scroll">
        <span
          v-for="cat in categories"
          :key="cat.key"
          :class="['category-tag', { active: activeCategory === cat.key }]"
          @click="switchCategory(cat.key)"
        >
          {{ cat.label }}
        </span>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <van-search v-model="searchKeyword" placeholder="搜索模板名称" shape="round" @search="doSearch" />
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="loadTemplates(activeCategory)">
      <!-- 模板列表 -->
      <van-grid :column-num="2" :gutter="10">
        <van-grid-item v-for="item in templates" :key="item.id">
          <div class="template-card">
            <div class="image-wrapper">
              <!-- 懒加载图片（先渲染） -->
              <img
                :data-src="getImageUrl(item.jpg_path)"
                class="cover-img"
                alt=""
                loading="lazy"
                @load="$event.target.classList.add('loaded')"
              />
              <!-- 骨架屏占位（覆盖在图片上） -->
              <div class="skeleton-placeholder"></div>
            </div>
            <div class="info">
              <div class="title van-ellipsis">{{ item.name }}</div>
              <div class="action-bar">
                <button class="btn-action" @click="handleBuy(item, 'download')">下载模板</button>
                <button class="btn-action btn-custom" @click="handleBuy(item, 'custom_service')">找人代做</button>
              </div>
            </div>
          </div>
        </van-grid-item>
      </van-grid>

      <!-- 加载更多提示 -->
      <div v-if="loadingMore" class="load-more">
        <van-loading size="20">加载中...</van-loading>
      </div>
      <div v-else-if="!hasMore && templates.length > 0" class="load-more done">
        已全部加载
      </div>
      <div v-else-if="templates.length === 0 && !loading" class="load-more empty">
        暂无模板
      </div>
    </van-pull-refresh>

    <van-dialog v-model:show="showCustomForm" title="填写代做需求" show-cancel-button @confirm="submitCustomOrder">
      <van-field v-model="customReqs" type="textarea" rows="3" placeholder="请填写您的学校、专业、求职意向及内容重点..." />
    </van-dialog>

    <van-popup v-model:show="showCashier" round position="bottom" :style="{ height: '45%' }" @closed="stopPolling">
      <div class="cashier-panel">
        <h3 class="panel-title">{{ currentOrder?.type === 'custom_service' ? '定制代做服务' : '模板自助下载' }}</h3>
        <div class="price-display">¥ {{ currentOrder?.amount || '0.00' }}</div>

        <div v-if="paymentStatus === 'paying' && payQrcode" class="qrcode-section">
          <img :src="payQrcode" class="qrcode-img" />
          <p class="qrcode-tip">微信扫码支付 ¥{{ currentOrder?.amount }}</p>
        </div>

        <div v-if="paymentStatus === 'paying'" class="qrcode-tip-loading">
          <van-loading type="spinner" size="16" /> 等待扫码支付...
        </div>

        <div v-if="paymentStatus === 'pending'" class="pay-actions">
          <p v-if="payError" class="pay-error-tip">{{ payError }}</p>
          <van-button type="success" block round @click="executeMockPay">
            (测试) 模拟支付 ¥{{ currentOrder?.amount }}
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.resume-list { padding: 10px; min-height: calc(100vh - 96px); padding-bottom: 70px; }

/* 分类筛选栏 */
.category-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  margin-bottom: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 8px 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.category-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
}
.category-scroll::-webkit-scrollbar { display: none; }
.category-tag {
  display: inline-block;
  padding: 5px 14px;
  font-size: 13px;
  border-radius: 16px;
  background: #f2f3f5;
  color: #646566;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.category-tag.active {
  background: #1989fa;
  color: #fff;
}

/* 搜索栏 */
.search-bar {
  margin-bottom: 12px;
}

/* 覆盖 van-grid-item 默认样式 */
.van-grid-item {
  padding: 5px !important;
}

/* 模板卡片 */
.template-card {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: transform 0.2s;
}

.image-wrapper {
  width: 100%;
  aspect-ratio: 210 / 297;
  overflow: hidden;
  position: relative;
  background: #f2f3f5;
  flex-shrink: 0;
}

/* 骨架屏占位（覆盖在图片上） */
.skeleton-placeholder {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s ease-in-out infinite;
  transition: opacity 0.3s;
}

.image-wrapper:has(.cover-img.loaded) .skeleton-placeholder {
  opacity: 0;
  pointer-events: none;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.3s;
  display: block;
}

.cover-img.loaded {
  opacity: 1;
}

.info { padding: 10px; }
.title { font-size: 13px; color: #323233; margin-bottom: 8px; font-weight: 500; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.action-bar { display: flex; justify-content: center; align-items: center; gap: 8px; }

/* 原生按钮样式（替代 van-button 解决事件拦截问题） */
.btn-action {
  flex: 1;
  padding: 6px 12px;
  font-size: 12px;
  border: 1px solid #1989fa;
  border-radius: 4px;
  background: #fff;
  color: #1989fa;
  cursor: pointer;
  line-height: 1.4;
  text-align: center;
  transition: all 0.2s;
}
.btn-action:active {
  background: #1989fa;
  color: #fff;
}
.btn-action.btn-custom {
  border-color: #ff976a;
  color: #ff976a;
}
.btn-action.btn-custom:active {
  background: #ff976a;
  color: #fff;
}

/* 加载更多 */
.load-more {
  text-align: center;
  padding: 20px;
  color: #999;
  font-size: 13px;
}
.load-more.empty {
  padding: 40px 20px;
}

/* 收银台 */
.cashier-panel { padding: 20px; text-align: center; }
.panel-title { margin: 0; color: #323233; font-size: 16px; font-weight: normal; }
.price-display { font-size: 36px; font-weight: bold; color: #ee0a24; margin: 15px 0 25px; }
.pay-actions { padding: 0 15px; }
.pay-error-tip { font-size: 12px; color: #999; margin-bottom: 10px; }
.qrcode-section { margin: 10px 0; }
.qrcode-img { width: 180px; height: 180px; display: block; margin: 0 auto; }
.qrcode-tip { font-size: 14px; color: #666; margin-top: 8px; }
.qrcode-tip-loading { font-size: 13px; color: #999; margin-top: 5px; display: flex; align-items: center; justify-content: center; gap: 6px; }
</style>
