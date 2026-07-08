<script setup>
import { ref } from 'vue'
import { showToast, showLoadingToast, closeToast } from 'vant'
import request from '../api/request.js'

const emit = defineEmits(['register-success'])

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const inviteCode = ref('')

const doRegister = async () => {
  if (!username.value || !password.value) {
    showToast('请填写用户名和密码')
    return
  }
  if (password.value.length < 6) {
    showToast('密码至少6位')
    return
  }
  if (password.value !== confirmPassword.value) {
    showToast('两次密码不一致')
    return
  }
  showLoadingToast({ message: '注册中...', forbidClick: true })
  try {
    const payload = {
      username: username.value,
      password: password.value,
    }
    if (inviteCode.value) {
      payload.ref_code = inviteCode.value
    }
    const res = await request.post('/auth/register', payload)
    closeToast()
    const { token, user } = res.data
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    showToast('注册成功')
    emit('register-success', user)
  } catch (e) {
    closeToast()
    showToast(e.response?.data?.detail || '注册失败')
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-header">
      <h2>注册账号</h2>
      <p>加入简历模板社区</p>
    </div>

    <van-form @submit="doRegister" class="auth-form">
      <van-cell-group inset>
        <van-field
          v-model="username"
          label="用户名"
          placeholder="设置用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        />
        <van-field
          v-model="password"
          type="password"
          label="密码"
          placeholder="至少6位密码"
          :rules="[
            { required: true, message: '请输入密码' },
            { validator: (v) => v.length >= 6, message: '密码至少6位' },
          ]"
        />
        <van-field
          v-model="confirmPassword"
          type="password"
          label="确认密码"
          placeholder="再次输入密码"
          :rules="[
            { required: true, message: '请确认密码' },
            { validator: (v) => v === password.value, message: '两次密码不一致' },
          ]"
        />
        <van-field
          v-model="inviteCode"
          label="邀请码(选填)"
          placeholder="有邀请人时填写"
        />
      </van-cell-group>

      <div class="auth-action">
        <van-button round block type="primary" native-type="submit">
          注册
        </van-button>
      </div>
    </van-form>

    <div class="auth-footer">
      已有账号？<a href="#" @click.prevent="$emit('register-success', null)">返回登录</a>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  background: #f7f8fa;
  display: flex;
  flex-direction: column;
  padding: 60px 20px 20px;
}
.auth-header { text-align: center; margin-bottom: 30px; }
.auth-header h2 { font-size: 24px; color: #1989fa; margin: 0 0 8px; }
.auth-header p { font-size: 14px; color: #969799; margin: 0; }
.auth-form { margin-bottom: 20px; }
.auth-action { padding: 30px 16px 0; }
.auth-footer { text-align: center; font-size: 14px; color: #646566; }
.auth-footer a { color: #1989fa; }
</style>