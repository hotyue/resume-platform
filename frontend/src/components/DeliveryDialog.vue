<script setup>
import { ref, watch, computed } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../api/request.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  orderNo: { type: String, default: '' },
  orderAmount: { type: Number, default: 0 },
  orderName: { type: String, default: '' },
})

const emit = defineEmits(['update:show', 'success'])

// 文件状态
const pdfFile = ref(null)
const wordFile = ref(null)
const remark = ref('')
const uploading = ref(false)
const pdfDragOver = ref(false)
const wordDragOver = ref(false)

// 上传进度
const uploadProgress = ref(0)

// 内联确认状态
const confirming = ref(false)

const ALLOWED_PDF = ['.pdf']
const ALLOWED_WORD = ['.doc', '.docx']
const MAX_SIZE = 10 * 1024 * 1024 // 10MB

// 校验文件扩展名
const checkExtension = (file, type) => {
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  const allowed = type === 'pdf' ? ALLOWED_PDF : ALLOWED_WORD
  return allowed.includes(ext)
}

// 校验文件大小
const checkSize = (file) => file.size <= MAX_SIZE

// 格式化文件大小
const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

// PDF 处理
const handlePdfSelect = (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  if (!checkExtension(file, 'pdf')) {
    showToast(`PDF 仅支持 .pdf 格式（当前: ${file.name}）`)
    return
  }
  if (!checkSize(file)) {
    showToast(`PDF 文件过大（${formatSize(file.size)}），最大 10MB`)
    return
  }
  pdfFile.value = file
}

const handlePdfDrag = (e) => {
  e.preventDefault()
  e.stopPropagation()
  if (e.type === 'dragover' || e.type === 'dragenter') {
    pdfDragOver.value = true
  } else {
    pdfDragOver.value = false
    const file = e.dataTransfer?.files?.[0]
    if (file) {
      if (!checkExtension(file, 'pdf')) {
        showToast(`PDF 仅支持 .pdf 格式（当前: ${file.name}）`)
        return
      }
      if (!checkSize(file)) {
        showToast(`PDF 文件过大（${formatSize(file.size)}），最大 10MB`)
        return
      }
      pdfFile.value = file
    }
  }
}

const clearPdf = () => {
  pdfFile.value = null
}

// Word 处理
const handleWordSelect = (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  if (!checkExtension(file, 'word')) {
    showToast(`Word 仅支持 .doc / .docx 格式（当前: ${file.name}）`)
    return
  }
  if (!checkSize(file)) {
    showToast(`Word 文件过大（${formatSize(file.size)}），最大 10MB`)
    return
  }
  wordFile.value = file
}

const handleWordDrag = (e) => {
  e.preventDefault()
  e.stopPropagation()
  if (e.type === 'dragover' || e.type === 'dragenter') {
    wordDragOver.value = true
  } else {
    wordDragOver.value = false
    const file = e.dataTransfer?.files?.[0]
    if (file) {
      if (!checkExtension(file, 'word')) {
        showToast(`Word 仅支持 .doc / .docx 格式（当前: ${file.name}）`)
        return
      }
      if (!checkSize(file)) {
        showToast(`Word 文件过大（${formatSize(file.size)}），最大 10MB`)
        return
      }
      wordFile.value = file
    }
  }
}

const clearWord = () => {
  wordFile.value = null
}

// 是否可以提交
const canSubmit = computed(() => pdfFile.value && wordFile.value && !uploading.value)

// 第一步：显示内联确认
const handleSubmit = () => {
  confirming.value = true
}

// 第二步：确认后执行上传
const confirmSubmit = async () => {
  confirming.value = false
  uploading.value = true
  uploadProgress.value = 0

  try {
    const formData = new FormData()
    formData.append('order_no', props.orderNo)
    formData.append('pdf_file', pdfFile.value)
    formData.append('word_file', wordFile.value)
    if (remark.value) {
      formData.append('remark', remark.value)
    }

    const totalSize = pdfFile.value.size + wordFile.value.size

    await request.post('/creator/deliver', formData, {
      onUploadProgress: (e) => {
        uploadProgress.value = Math.round((e.loaded / totalSize) * 100)
      },
    })

    // 上传成功 — 关闭弹窗
    emit('update:show', false)
    showSuccessToast('已交付，等待买家验收')
    emit('success')
  } catch (e) {
    const msg = e.response?.data?.detail || '交付失败'
    showToast(msg)
    console.error('Delivery failed:', e.response?.data || e.message)
  } finally {
    uploading.value = false
    uploadProgress.value = 0
  }
}

// 取消确认
const cancelConfirm = () => {
  confirming.value = false
}

// 关闭时清空
watch(() => props.show, (val) => {
  if (!val) {
    pdfFile.value = null
    wordFile.value = null
    remark.value = ''
    uploading.value = false
  }
})
</script>

<template>
  <div v-if="show" class="delivery-overlay" @click.self="!uploading && $emit('update:show', false)">
    <div class="delivery-dialog-mask">
      <div class="delivery-dialog">
        <div class="dialog-header">
          <div class="header-title">
            <h3>交付订单</h3>
            <div class="order-info">
              <span class="order-no">{{ orderNo }}</span>
              <span v-if="orderName" class="order-name">{{ orderName }}</span>
            </div>
          </div>
          <span class="close-btn" :class="{ 'close-disabled': uploading }" @click="!uploading && $emit('update:show', false)">✕</span>
        </div>

        <div class="dialog-body">
          <!-- PDF 上传 -->
          <div class="file-upload-section">
            <div class="file-label">
              <span class="label-text">📄 PDF 文件</span>
              <span class="label-hint">（必选，仅 .pdf）</span>
            </div>
            <div
              class="drop-zone"
              :class="{ 'has-file': pdfFile, 'drag-over': pdfDragOver }"
              @dragover="handlePdfDrag"
              @dragenter="handlePdfDrag"
              @dragleave="handlePdfDrag"
              @drop="handlePdfDrag"
              @click="$refs.pdfInput?.click()"
            >
              <input
                ref="pdfInput"
                type="file"
                accept=".pdf"
                class="file-input"
                @change="handlePdfSelect"
              />
              <div v-if="!pdfFile" class="drop-placeholder">
                <span class="drop-icon">📤</span>
                <span>拖拽 PDF 到此处，或点击选择</span>
              </div>
              <div v-else class="file-info">
                <div class="file-name">{{ pdfFile.name }}</div>
                <div class="file-size">{{ formatSize(pdfFile.size) }}</div>
                <span class="file-remove" @click.stop="clearPdf">✕ 移除</span>
              </div>
            </div>
          </div>

          <!-- Word 上传 -->
          <div class="file-upload-section">
            <div class="file-label">
              <span class="label-text">📝 Word 文件</span>
              <span class="label-hint">（必选，.doc / .docx）</span>
            </div>
            <div
              class="drop-zone"
              :class="{ 'has-file': wordFile, 'drag-over': wordDragOver }"
              @dragover="handleWordDrag"
              @dragenter="handleWordDrag"
              @dragleave="handleWordDrag"
              @drop="handleWordDrag"
              @click="$refs.wordInput?.click()"
            >
              <input
                ref="wordInput"
                type="file"
                accept=".doc,.docx"
                class="file-input"
                @change="handleWordSelect"
              />
              <div v-if="!wordFile" class="drop-placeholder">
                <span class="drop-icon">📤</span>
                <span>拖拽 Word 到此处，或点击选择</span>
              </div>
              <div v-else class="file-info">
                <div class="file-name">{{ wordFile.name }}</div>
                <div class="file-size">{{ formatSize(wordFile.size) }}</div>
                <span class="file-remove" @click.stop="clearWord">✕ 移除</span>
              </div>
            </div>
          </div>

          <!-- 备注 -->
          <div class="remark-section">
            <div class="file-label">
              <span class="label-text">💬 备注</span>
              <span class="label-hint">（可选）</span>
            </div>
            <textarea
              v-model="remark"
              class="remark-textarea"
              placeholder="给买家的备注（选填）"
              rows="3"
            ></textarea>
          </div>

          <!-- 上传进度 -->
          <div v-if="uploading" class="progress-section">
            <div class="progress-header">
              <span class="progress-label">📤 上传中...</span>
              <span class="progress-percent">{{ uploadProgress }}%</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <div class="progress-detail">
              <span>PDF: {{ pdfFile ? formatSize(pdfFile.size) : '-' }}</span>
              <span>Word: {{ wordFile ? formatSize(wordFile.size) : '-' }}</span>
            </div>
          </div>

          <!-- 文件状态 -->
          <div class="upload-status" v-if="!uploading">
            <div class="status-item" :class="{ done: pdfFile }">
              <span class="status-icon">{{ pdfFile ? '✅' : '⬜' }}</span>
              <span>PDF: {{ pdfFile ? pdfFile.name : '未选择' }}</span>
            </div>
            <div class="status-item" :class="{ done: wordFile }">
              <span class="status-icon">{{ wordFile ? '✅' : '⬜' }}</span>
              <span>Word: {{ wordFile ? wordFile.name : '未选择' }}</span>
            </div>
          </div>
        </div>

        <div class="dialog-footer">
          <template v-if="uploading">
            <div class="uploading-box">
              <div class="uploading-icon">⏳</div>
              <div class="uploading-text">正在上传文件，请勿关闭页面...</div>
            </div>
          </template>
          <template v-else-if="!confirming">
            <button class="btn-cancel" @click="$emit('update:show', false)">取消</button>
            <button
              class="btn-submit"
              :class="{ 'btn-disabled': !canSubmit }"
              :disabled="!canSubmit"
              @click="handleSubmit"
            >
              确认交付
            </button>
          </template>
          <template v-else>
            <div class="confirm-box">
              <div class="confirm-icon">⚠️</div>
              <div class="confirm-text">交付后等待买家验收，验收通过后佣金进入7天冻结期</div>
              <div class="confirm-actions">
                <button class="btn-cancel" @click="cancelConfirm">再想想</button>
                <button class="btn-submit" @click="confirmSubmit">确定交付</button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.delivery-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 9000;
}

.delivery-dialog-mask {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 15px;
  background: rgba(0, 0, 0, 0.5);
}

.delivery-dialog {
  background: white;
  border-radius: 16px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.header-title {
  flex: 1;
  min-width: 0;
}

.dialog-header h3 {
  margin: 0;
  font-size: 17px;
  color: #323233;
}

.order-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.order-no {
  font-size: 12px;
  color: #969799;
  font-family: monospace;
}

.order-name {
  font-size: 12px;
  color: #646566;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-btn {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 4px 8px;
}

.dialog-body {
  padding: 20px;
}

.file-upload-section {
  margin-bottom: 18px;
}

.file-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.label-text {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}

.label-hint {
  font-size: 12px;
  color: #999;
}

.drop-zone {
  border: 2px dashed #dcdee0;
  border-radius: 10px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
}

.drop-zone:hover {
  border-color: #07c160;
  background: #f0f9f4;
}

.drop-zone.has-file {
  border-color: #07c160;
  background: #f0f9f4;
  border-style: solid;
}

.drop-zone.drag-over {
  border-color: #07c160;
  background: #e6f7ed;
  transform: scale(1.02);
}

.file-input {
  display: none;
}

.drop-placeholder .drop-icon {
  font-size: 28px;
  display: block;
  margin-bottom: 8px;
}

.drop-placeholder span:last-child {
  font-size: 13px;
  color: #999;
}

.file-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.file-name {
  font-size: 14px;
  color: #323233;
  font-weight: 500;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: #999;
}

.file-remove {
  font-size: 12px;
  color: #ee0a24;
  cursor: pointer;
  margin-top: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #fff1f0;
}

.remark-section {
  margin-bottom: 18px;
}

.remark-textarea {
  width: 100%;
  border: 1px solid #dcdee0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
}

.remark-textarea:focus {
  outline: none;
  border-color: #07c160;
}

.upload-status {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 12px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #999;
  padding: 4px 0;
}

.status-item.done {
  color: #07c160;
}

.dialog-footer {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}

.btn-cancel,
.btn-submit {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  background: #f7f8fa;
  color: #646566;
}

.btn-cancel:hover {
  background: #f2f3f5;
}

.btn-submit {
  background: #07c160;
  color: white;
}

.btn-submit:hover:not(.btn-disabled) {
  background: #06ad56;
}

.btn-disabled {
  background: #c8c9cc !important;
  color: #fff !important;
  cursor: not-allowed !important;
}

/* 内联确认框 */
.confirm-box {
  width: 100%;
}

.confirm-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 12px;
}

.confirm-text {
  font-size: 14px;
  color: #646566;
  text-align: center;
  line-height: 1.6;
  margin-bottom: 16px;
}

.confirm-actions {
  display: flex;
  gap: 12px;
}

/* 上传进度条 */
.progress-section {
  margin-bottom: 16px;
  padding: 16px;
  background: #f0f9f4;
  border-radius: 10px;
  border: 1px solid #b7e4c7;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.progress-label {
  font-size: 14px;
  font-weight: 500;
  color: #07c160;
}

.progress-percent {
  font-size: 18px;
  font-weight: 700;
  color: #07c160;
  font-family: monospace;
}

.progress-track {
  height: 8px;
  background: #dcdee0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #07c160, #05a84e);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #969799;
}

/* 上传中状态 */
.uploading-box {
  width: 100%;
  text-align: center;
  padding: 8px 0;
}

.uploading-icon {
  font-size: 32px;
  margin-bottom: 8px;
  animation: pulse 1.5s ease-in-out infinite;
}

.uploading-text {
  font-size: 14px;
  color: #646566;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.95); }
}
</style>
