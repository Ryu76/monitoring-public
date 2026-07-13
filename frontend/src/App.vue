<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { LayoutDashboard, Server, Users, AlertTriangle, LogOut, Sun, Moon, ShieldAlert } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const isLoginPage = computed(() => route.name === 'login')

const userInfo = computed(() => {
  const raw = localStorage.getItem('user_info')
  return raw ? JSON.parse(raw) : null
})

const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
  router.push('/login')
}

const isDark = ref(true)

const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme) {
    isDark.value = savedTheme === 'dark'
    document.documentElement.setAttribute('data-theme', savedTheme)
  }
})
</script>

<template>
  <!-- 로그인 화면은 사이드바 없이 전체 화면 -->
  <template v-if="isLoginPage">
    <RouterView />
  </template>

  <!-- 일반 화면: 사이드바 + 메인 -->
  <template v-else>
    <div class="sidebar">
      <div class="sidebar-logo">Nexus Mon</div>
      <ul class="nav-menu">
        <li>
          <RouterLink to="/" class="nav-link">
            <LayoutDashboard :size="20" /> 대시보드
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/servers" class="nav-link">
            <Server :size="20" /> 서버 상세
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/agents" class="nav-link">
            <Users :size="20" /> 에이전트 관리
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/events" class="nav-link">
            <AlertTriangle :size="20" /> 이벤트
          </RouterLink>
        </li>
        <li>
          <RouterLink to="/incidents" class="nav-link">
            <ShieldAlert :size="20" /> 인시던트
          </RouterLink>
        </li>
      </ul>
      
      <!-- 하단 사용자 정보 및 로그아웃 -->
      <div class="sidebar-footer">
        <div v-if="userInfo" class="user-info">
          <div class="user-avatar">{{ userInfo.user_name?.charAt(0) || 'U' }}</div>
          <div>
            <div class="user-name">{{ userInfo.user_name }}</div>
            <div class="user-dept">{{ userInfo.dept_name || userInfo.login_id }}</div>
          </div>
        </div>
        <button @click="toggleTheme" class="btn btn-outline" style="width: 100%; margin-top: 16px; padding: 8px;">
          <component :is="isDark ? Sun : Moon" :size="16" /> {{ isDark ? '밝은 화면' : '어두운 화면' }}
        </button>
        <button @click="logout" class="btn btn-outline" style="width: 100%; margin-top: 8px; padding: 8px;">
          <LogOut :size="16" /> 로그아웃
        </button>
      </div>
    </div>
    
    <div class="main-content">
      <RouterView />
    </div>
  </template>
</template>

<style scoped>
.sidebar-footer {
  margin-top: auto;
  padding-top: 24px;
  border-top: 1px solid var(--surface-border);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  color: white;
}

.user-name {
  font-weight: 600;
  font-size: 14px;
}

.user-dept {
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .sidebar-footer {
    display: none;
  }
}
</style>
