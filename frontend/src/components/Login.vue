<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const loginId = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const handleLogin = async () => {
  error.value = ''
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('username', loginId.value)
    formData.append('password', password.value)
    const res = await api.post('/api/v1/admin/auth/login', formData)
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('user_info', JSON.stringify(res.data.user_info))
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '로그인에 실패했습니다.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card glass-card animate-fade-in">
      <div class="login-logo">Nexus Mon</div>
      <p style="color: var(--text-secondary); text-align: center; margin-bottom: 32px;">통합 서버 모니터링 관리 시스템</p>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label>로그인 ID</label>
          <input v-model="loginId" type="text" placeholder="admin" required />
        </div>
        <div class="form-group">
          <label>비밀번호</label>
          <input v-model="password" type="password" placeholder="비밀번호 입력" required />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" class="btn btn-primary" style="width: 100%; padding: 14px;" :disabled="loading">
          {{ loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  width: 100%;
}

.login-card {
  width: 400px;
  padding: 48px 40px;
}

.login-logo {
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 8px;
  background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-group input {
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s ease;
}

.form-group input:focus {
  border-color: var(--accent-primary);
}

.error-text {
  color: var(--danger);
  font-size: 13px;
  margin: 0;
  text-align: center;
}
</style>
