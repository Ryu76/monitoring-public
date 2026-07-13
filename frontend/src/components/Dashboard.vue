<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../api'

interface SummaryData {
  total_servers: number
  normal: number
  warning: number
  critical: number
  unknown: number
  total_agents: number
  online_agents: number
  open_events: number
}

interface EventData {
  event_uid: string
  severity_code: string
  status_code: string
  title: string
  message: string
  first_occurred_at: string | null
  occurrence_count: number
}

const summary = ref<SummaryData | null>(null)
const events = ref<EventData[]>([])
const loading = ref(true)

const fetchData = async () => {
  loading.value = true
  try {
    const [summaryRes, eventsRes] = await Promise.all([
      api.get('/api/v1/dashboard/summary'),
      api.get('/api/v1/events', { params: { status: 'OPEN' } })
    ])
    summary.value = summaryRes.data.data
    events.value = eventsRes.data.data.slice(0, 10)
  } catch (e) {
    console.error('대시보드 데이터를 불러오지 못했습니다.', e)
  } finally {
    loading.value = false
  }
}

const severityColor = (code: string) => {
  switch (code) {
    case 'FATAL': return 'badge-fatal'
    case 'CRITICAL': return 'badge-fatal'
    case 'WARNING': return 'badge-warning'
    default: return 'badge-unknown'
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="container animate-fade-in">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <div>
        <h1 style="margin-bottom: 4px;">대시보드</h1>
        <p style="margin: 0;">인프라 상태 요약</p>
      </div>
      <button @click="fetchData" class="btn btn-outline">새로고침</button>
    </div>

    <div v-if="loading" style="text-align: center; padding: 80px; color: var(--text-secondary);">불러오는 중...</div>

    <template v-else-if="summary">
      <div class="grid-3" style="margin-bottom: 32px;">
        <div class="glass-card kpi-card">
          <div class="kpi-label">전체 서버</div>
          <div class="kpi-value">{{ summary.total_servers }}</div>
          <div class="kpi-detail">
            <span class="badge badge-normal">정상 {{ summary.normal }}</span>
            <span class="badge badge-warning" v-if="summary.warning">경고 {{ summary.warning }}</span>
            <span class="badge badge-fatal" v-if="summary.critical">위험 {{ summary.critical }}</span>
          </div>
        </div>
        <div class="glass-card kpi-card">
          <div class="kpi-label">활성 에이전트</div>
          <div class="kpi-value" :style="{ color: summary.online_agents === summary.total_agents ? 'var(--success)' : 'var(--warning)' }">
            {{ summary.online_agents }} <span style="font-size: 16px; color: var(--text-secondary);">/ {{ summary.total_agents }}</span>
          </div>
          <div class="kpi-detail">
            <span class="badge badge-normal">온라인</span>
          </div>
        </div>
        <div class="glass-card kpi-card">
          <div class="kpi-label">진행 중 이벤트</div>
          <div class="kpi-value" :style="{ color: summary.open_events > 0 ? 'var(--danger)' : 'var(--success)' }">
            {{ summary.open_events }}
          </div>
          <div class="kpi-detail">
            <span v-if="summary.open_events === 0" class="badge badge-normal">이상 없음</span>
            <span v-else class="badge badge-fatal">조치 필요</span>
          </div>
        </div>
      </div>

      <div class="glass-card" style="animation-delay: 0.2s;">
        <h3 style="margin-bottom: 16px;">최근 이벤트</h3>
        <div v-if="events.length === 0" style="color: var(--text-secondary); padding: 24px; text-align: center;">
          현재 진행 중인 이벤트가 없습니다.
        </div>
        <table v-else style="width: 100%; text-align: left; border-collapse: collapse;">
          <thead>
            <tr style="border-bottom: 1px solid var(--surface-border);">
              <th class="th">심각도</th>
              <th class="th">제목</th>
              <th class="th">최초 발생</th>
              <th class="th">반복</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="evt in events" :key="evt.event_uid" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
              <td class="td"><span :class="['badge', severityColor(evt.severity_code)]">{{ evt.severity_code }}</span></td>
              <td class="td" style="font-weight: 500;">{{ evt.title }}</td>
              <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ evt.first_occurred_at?.replace('T', ' ').slice(0, 19) ?? '-' }}</td>
              <td class="td">{{ evt.occurrence_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kpi-label {
  font-size: 13px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 1px;
}
.kpi-value {
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
}
.kpi-detail {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.th {
  padding: 12px 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.td {
  padding: 14px 8px;
}
</style>
