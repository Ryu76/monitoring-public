<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../api'

interface EventItem {
  event_uid: string
  server_id: number
  target_type_code: string
  severity_code: string
  status_code: string
  title: string
  message: string
  first_occurred_at: string | null
  last_occurred_at: string | null
  recovered_at: string | null
  occurrence_count: number
  ack_at: string | null
  incident_id: number | null
}

const events = ref<EventItem[]>([])
const loading = ref(true)
const filter = ref('OPEN')
const creatingIncident = ref<string | null>(null)

const fetchEvents = async () => {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filter.value !== 'ALL') params.status = filter.value
    const res = await api.get('/api/v1/events', { params })
    events.value = res.data.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const ackEvent = async (uid: string) => {
  try {
    await api.put(`/api/v1/events/${uid}/ack`)
    await fetchEvents()
  } catch (e) {
    console.error(e)
  }
}

const createIncident = async (evt: EventItem) => {
  creatingIncident.value = evt.event_uid
  try {
    await api.post(`/api/v1/events/${evt.event_uid}/incident`, {
      incident_title: evt.title,
      impact_code: evt.severity_code === 'FATAL' || evt.severity_code === 'CRITICAL' ? 'HIGH' : 'MEDIUM',
      cause_code: 'UNKNOWN',
      action_note: `이벤트에서 인시던트를 생성했습니다. ${evt.message || ''}`.trim()
    })
    await fetchEvents()
  } catch (e) {
    console.error(e)
  } finally {
    creatingIncident.value = null
  }
}

const severityBadge = (code: string) => {
  switch (code) {
    case 'FATAL':
    case 'CRITICAL':
      return 'badge-fatal'
    case 'WARNING':
      return 'badge-warning'
    default:
      return 'badge-unknown'
  }
}

const statusBadge = (code: string) => {
  switch (code) {
    case 'OPEN': return 'badge-fatal'
    case 'CLOSED': return 'badge-normal'
    default: return 'badge-unknown'
  }
}

const formatDate = (value: string | null) => value?.replace('T', ' ').slice(0, 19) ?? '-'

onMounted(fetchEvents)
</script>

<template>
  <div class="container animate-fade-in">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 16px; flex-wrap: wrap;">
      <div>
        <h1 style="margin-bottom: 4px;">이벤트 관리</h1>
        <p style="margin: 0;">자동 감지된 장애/경고 이벤트를 확인하고 인시던트로 전환합니다.</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <button :class="['btn', filter === 'OPEN' ? 'btn-primary' : 'btn-outline']" @click="filter = 'OPEN'; fetchEvents()">진행중</button>
        <button :class="['btn', filter === 'CLOSED' ? 'btn-primary' : 'btn-outline']" @click="filter = 'CLOSED'; fetchEvents()">복구됨</button>
        <button :class="['btn', filter === 'ALL' ? 'btn-primary' : 'btn-outline']" @click="filter = 'ALL'; fetchEvents()">전체</button>
      </div>
    </div>

    <div v-if="loading" style="text-align: center; padding: 80px; color: var(--text-secondary);">불러오는 중...</div>

    <div v-else-if="events.length === 0" class="glass-card" style="text-align: center; padding: 60px; color: var(--text-secondary);">
      조건에 맞는 이벤트가 없습니다.
    </div>

    <div v-else class="glass-card table-wrap">
      <table>
        <thead>
          <tr>
            <th class="th">심각도</th>
            <th class="th">상태</th>
            <th class="th">제목</th>
            <th class="th">메시지</th>
            <th class="th">최초 발생</th>
            <th class="th">반복</th>
            <th class="th">인시던트</th>
            <th class="th">조치</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="evt in events" :key="evt.event_uid">
            <td class="td"><span :class="['badge', severityBadge(evt.severity_code)]">{{ evt.severity_code }}</span></td>
            <td class="td"><span :class="['badge', statusBadge(evt.status_code)]">{{ evt.status_code }}</span></td>
            <td class="td title-cell">{{ evt.title }}</td>
            <td class="td message-cell">{{ evt.message }}</td>
            <td class="td muted">{{ formatDate(evt.first_occurred_at) }}</td>
            <td class="td">{{ evt.occurrence_count }}</td>
            <td class="td">
              <span v-if="evt.incident_id" class="badge badge-normal">#{{ evt.incident_id }}</span>
              <button
                v-else
                @click="createIncident(evt)"
                class="btn btn-outline compact-btn"
                :disabled="creatingIncident === evt.event_uid"
              >
                생성
              </button>
            </td>
            <td class="td">
              <button v-if="evt.status_code === 'OPEN' && !evt.ack_at" @click="ackEvent(evt.event_uid)" class="btn btn-outline compact-btn">확인</button>
              <span v-else class="muted">{{ evt.ack_at ? '확인됨' : '-' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  min-width: 980px;
  text-align: left;
  border-collapse: collapse;
}
tr {
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
thead tr {
  border-bottom: 1px solid var(--surface-border);
}
.th {
  padding: 14px 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.td {
  padding: 14px 8px;
  vertical-align: middle;
}
.title-cell {
  font-weight: 600;
  min-width: 180px;
}
.message-cell {
  color: var(--text-secondary);
  font-size: 13px;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--text-secondary);
  font-size: 13px;
}
.compact-btn {
  padding: 6px 12px;
  font-size: 12px;
}
</style>
