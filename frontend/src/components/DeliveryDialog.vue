<template>
  <van-dialog v-model:show="dialogShow" :show-confirm-button="false" :show-cancel-button="true"
    cancel-button-text="取消" class="delivery-dialog"
    @cancel="onCancel">
    <div class="delivery-form">
      <div class="delivery-header">
        <van-icon name="passed" size="24" color="#07c160" />
        <span>提交交付</span>
      </div>

      <div class="order-info" v-if="orderName">
        <span>订单模板：{{ orderName }}</span>
        <span>订单号：{{ orderNo }}</span>
      </div>

      <van-cell-group inset>
        <van-cell title="PDF 文件" required>
          <template #value>
            <div class="file-picker">
              <span v-if="pdfName" class="file-name">{{ pdfName }}</span>
              <span v-else class="file-placeholder">选择 .pdf 文件</span>
              <input ref="pdfInput" type="file" accept=".pdf" @change="onPdfChange" class="hidden-input" />
              <van-button size="mini" type="primary" plain @click="triggerPdf">选择</van-button>
            </div>
          </template>
        </van-cell>

        <van-cell title="Word 文件" required>
          <template #value>
            <div class="file-picker">
              <span v-if="wordName" class="file-name">{{ wordName }}</span>
              <span v-else class="file-placeholder">选择 .doc/.docx 文件</span>
              <input ref="wordInput" type="file" accept=".doc,.docx" @change="onWordChange" class="hidden-input" />
              <van-button size="mini" type="primary" plain @click="triggerWord">选择</van-button>
            </div>
          </template>
        </van-cell>

        <van-cell title="备注" label-position="top">
          <template #value>
            <van-field v-model="remark" rows="2" type="textarea" placeholder="选填：交付说明" />
          </template>
        </van-cell>
      </van-cell-group>

      <div class="delivery-notice">
        交付后等待买家验收，验收通过后佣金进入制作者账号余额
      </div>

      <!-- 上传进度条 -->
      <div v-if="showProgress" class="progress-section">
        <div class="progress-header">
          <span class="progress-label">上传中...</span>
          <span class="progress-pct">{{ uploadProgress }}%</span>
        </div>
        <van-progress
          :percentage="uploadProgress"
          color="linear-gradient(90deg, #1989fa, #07c160)"
          stroke-width="8"
          pivot-text="上传中"
        />
        <div class="progress-detail" v-if="uploadingText">
          {{ uploadingText }}
        </div>
      </div>

      <div class="dialog-footer">
        <van-button type="primary" block round :loading="submitting" :disabled="submitting" @click="submitDelivery">
          {{ submitting ? '上传中...' : '确定交付' }}
        </van-button>
      </div>
    </div>
  </van-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { getToken } from '../api/request.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  orderNo: { type: String, default: '' },
  orderAmount: { type: Number, default: 0 },
  orderName: { type: String, default: '' },
})

const emit = defineEmits(['update:show', 'success'])

const dialogShow = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const pdfFile = ref(null)
const wordFile = ref(null)
const pdfName = ref('')
const wordName = ref('')
const pdfSize = ref(0)
const wordSize = ref(0)
const remark = ref('')
const submitting = ref(false)
const pdfInput = ref(null)
const wordInput = ref(null)

// 进度条
const showProgress = ref(false)
const uploadProgress = ref(0)
const uploadingText = ref('')

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

watch(() => props.show, (val) => {
  if (val) {
    resetForm()
  }
})

function resetForm() {
  pdfFile.value = null
  wordFile.value = null
  pdfName.value = ''
  wordName.value = ''
  pdfSize.value = 0
  wordSize.value = 0
  remark.value = ''
  submitting.value = false
  showProgress.value = false
  uploadProgress.value = 0
  uploadingText.value = ''
}

function triggerPdf() {
  pdfInput.value?.click()
}

function triggerWord() {
  wordInput.value?.click()
}

function onPdfChange(e) {
  const file = e.target.files?.[0]
  if (file) {
    pdfFile.value = file
    pdfName.value = file.name
    pdfSize.value = file.size
  }
}

function onWordChange(e) {
  const file = e.target.files?.[0]
  if (file) {
    wordFile.value = file
    wordName.value = file.name
    wordSize.value = file.size
  }
}

function onCancel() {
  resetForm()
  emit('update:show', false)
}

async function submitDelivery() {
  if (!pdfFile.value) {
    showToast('请选择 PDF 文件')
    return
  }
  if (!wordFile.value) {
    showToast('请选择 Word 文件')
    return
  }
  if (!props.orderNo) {
    showToast('订单号异常')
    return
  }

  submitting.value = true
  showProgress.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('order_no', props.orderNo)
    formData.append('pdf_file', pdfFile.value)
    formData.append('word_file', wordFile.value)
    if (remark.value) {
      formData.append('remark', remark.value)
    }

    const token = getToken()
    const baseURL = import.meta.env.VITE_API_BASE || '/api/v1'

    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', baseURL + '/creator/deliver')
      xhr.setRequestHeader('Authorization', 'Bearer ' + token)

      // 上传进度
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100)
          uploadProgress.value = pct
          uploadingText.value = `${formatSize(e.loaded)} / ${formatSize(e.total)}`
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch {
            resolve({ status: 'success' })
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText)
            reject(new Error(err.detail || `HTTP ${xhr.status}`))
          } catch {
            reject(new Error(`HTTP ${xhr.status}`))
          }
        }
      }

      xhr.onerror = () => reject(new Error('网络连接失败'))
      xhr.ontimeout = () => reject(new Error('上传超时'))
      xhr.timeout = 120000

      xhr.send(formData)
    })

    uploadProgress.value = 100
    showSuccessToast('交付成功')
    emit('update:show', false)
    emit('success')
  } catch (e) {
    showFailToast(e.message || '交付失败，请重试')
  } finally {
    submitting.value = false
    setTimeout(() => {
      showProgress.value = false
    }, 1500)
  }
}
</script>

<style scoped>
.delivery-dialog { max-width: 90vw; }
.delivery-form { padding: 15px; min-height: 200px; }
.delivery-header { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 18px; font-weight: bold; margin-bottom: 15px; }
.order-info { font-size: 12px; color: #999; text-align: center; margin-bottom: 10px; }
.order-info span { display: block; margin: 2px 0; }
.file-picker { display: flex; align-items: center; gap: 8px; }
.file-name { font-size: 12px; color: #07c160; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-placeholder { font-size: 12px; color: #999; }
.hidden-input { display: none; }
.delivery-notice { font-size: 12px; color: #666; background: #fffbe6; padding: 8px 12px; border-radius: 6px; margin: 12px 0; border: 1px solid #ffe58f; }
.dialog-footer { margin-top: 15px; }

.progress-section { margin: 12px 0; padding: 8px 12px; background: #f0f7ff; border-radius: 8px; border: 1px solid #d9ecff; }
.progress-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.progress-label { font-size: 13px; color: #1989fa; font-weight: 500; }
.progress-pct { font-size: 13px; color: #1989fa; font-weight: bold; }
.progress-detail { font-size: 11px; color: #999; text-align: center; margin-top: 6px; }
</style>
