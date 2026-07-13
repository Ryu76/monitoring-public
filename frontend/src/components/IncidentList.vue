<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'

interface IncidentAction {
  action_id: number
  incident_id: number
  action_user_id: number | null
  action_note: string
  action_at: string | null
}

interface LinkedEvent {
  event_uid: string
  severity_code: string
  status_code: string
  title: string
  message: string
  first_occurred_at: string | null
}

interface IncidentItem {
  incident_id: number
  incident_title: string
  status_code: string
  impact_code: string | null
  cause_code: string | null
  assigned_to: number | null
  detected_at: string | null
  resolved_at: string | null
  closed_at: string | null
  latest_action_note?: string | null
  latest_action_at?: string | null
  actions?: IncidentAction[]
  events?: LinkedEvent[]
}

const incidents = ref<IncidentItem[]>([])
const selectedIncident = ref<IncidentItem | null>(null)
const loading = ref(true)
const detailLoading = ref(false)
const saving = ref(false)

const editForm = reactive({
  incident_title: '',
  status_code: 'OPEN',
  impact_code: 'MEDIUM',
  cause_code: 'UNKNOWN',
  assigned_to: ''
})

const actionForm = reactive({
  action_note: '',
  status_code: '',
  cause_code: '',
  assigned_to: ''
})

const selectedId = computed(() => selectedIncident.value?.incident_id ?? null)

const fetchIncidents = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/v1/incidents')
    incidents.value = res.data.data
    if (!selectedIncident.value && incidents.value.length > 0) {
      await selectIncident(incidents.value[0].incident_id)
    } else if (selectedIncident.value) {
      await selectIncident(selectedIncident.value.incident_id)
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const selectIncident = async (id: number) => {
  detailLoading.value = true
  try {
    const res = await api.get(`/api/v1/incidents/${id}`)
    const incident = res.data.data as IncidentItem
    selectedIncident.value = incident
    fillEditForm(incident)
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

const fillEditForm = (incident: IncidentItem) => {
  editForm.incident_title = incident.incident_title || ''
  editForm.status_code = incident.status_code || 'OPEN'
  editForm.impact_code = incident.impact_code || 'MEDIUM'
  editForm.cause_code = incident.cause_code || 'UNKNOWN'
  editForm.assigned_to = incident.assigned_to == null ? '' : String(incident.assigned_to)
}

const saveIncident = async () => {
  if (!selectedIncident.value) return
  saving.value = true
  try {
    await api.put(`/api/v1/incidents/${selectedIncident.value.incident_id}`, {
      incident_title: editForm.incident_title,
      status_code: editForm.status_code,
      impact_code: editForm.impact_code,
      cause_code: editForm.cause_code,
      assigned_to: editForm.assigned_to === '' ? null : Number(editForm.assigned_to)
    })
    await fetchIncidents()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

const addAction = async () => {
  if (!selectedIncident.value || !actionForm.action_note.trim()) return
  saving.value = true
  try {
    await api.post(`/api/v1/incidents/${selectedIncident.value.incident_id}/actions`, {
      action_note: actionForm.action_note,
      status_code: actionForm.status_code || null,
      cause_code: actionForm.cause_code || null,
      assigned_to: actionForm.assigned_to === '' ? null : Number(actionForm.assigned_to)
    })
    actionForm.action_note = ''
    actionForm.status_code = ''
    actionForm.cause_code = ''
    actionForm.assigned_to = ''
    await fetchIncidents()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

const statusBadge = (code: string) => {
  switch (code) {
    case 'OPEN': return 'badge-fatal'
    case 'IN_PROGRESS': return 'badge-warning'
    case 'RESOLVED':
    case 'CLOSED':
      return 'badge-normal'
    default:
      return 'badge-unknown'
  }
}

const impactBadge = (code: string | null) => {
  switch (code) {
    case 'HIGH': return 'badge-fatal'
    case 'MEDIUM': return 'badge-warning'
    case 'LOW': return 'badge-normal'
    default: return 'badge-unknown'
  }
}

const formatDate = (value: string | null | undefined) => value?.replace('T', ' ').slice(0, 19) ?? '-'

onMounted(fetchIncidents)
</script>

<template>
  <div class="container animate-fade-in">
    <div class="page-header">
      <div>
        <h1>인시던트 관리</h1>
        <p>이벤트를 장애 사건으로 묶고 담당자, 조치 상태, 원인 분석, 조치 이력을 관리합니다.</p>
      </div>
      <button @click="fetchIncidents" class="btn btn-outline">새로고침</button>
    </div>

    <div v-if="loading" class="loading">불러오는 중...</div>

    <div v-else-if="incidents.length === 0" class="glass-card empty">
      등록된 인시던트가 없습니다. 이벤트 화면에서 인시던트를 생성할 수 있습니다.
    </div>

    <div v-else class="incident-layout">
      <div class="glass-card list-panel">
        <h3>인시던트 목록</h3>
        <button
          v-for="inc in incidents"
          :key="inc.incident_id"
          @click="selectIncident(inc.incident_id)"
          :class="['incident-item', selectedId === inc.incident_id ? 'active' : '']"
        >
          <div class="incident-row">
            <strong>#{{ inc.incident_id }} {{ inc.incident_title }}</strong>
            <span :class="['badge', statusBadge(inc.status_code)]">{{ inc.status_code }}</span>
          </div>
          <div class="incident-meta">
            <span :class="['badge', impactBadge(inc.impact_code)]">{{ inc.impact_code || 'UNKNOWN' }}</span>
            <span>담당자 {{ inc.assigned_to ?? '-' }}</span>
            <span>{{ formatDate(inc.detected_at) }}</span>
          </div>
          <div v-if="inc.latest_action_note" class="latest-action">{{ inc.latest_action_note }}</div>
        </button>
      </div>

      <div class="detail-column">
        <div v-if="detailLoading" class="glass-card loading">상세 정보를 불러오는 중...</div>

        <template v-else-if="selectedIncident">
          <div class="glass-card">
            <h3>기본 정보</h3>
            <div class="form-grid">
              <label>
                제목
                <input v-model="editForm.incident_title" class="field" />
              </label>
              <label>
                조치 상태
                <select v-model="editForm.status_code" class="field">
                  <option value="OPEN">진행중</option>
                  <option value="IN_PROGRESS">조치중</option>
                  <option value="RESOLVED">해결됨</option>
                  <option value="CLOSED">종료</option>
                </select>
              </label>
              <label>
                영향도
                <select v-model="editForm.impact_code" class="field">
                  <option value="LOW">낮음</option>
                  <option value="MEDIUM">보통</option>
                  <option value="HIGH">높음</option>
                </select>
              </label>
              <label>
                원인 분석
                <select v-model="editForm.cause_code" class="field">
                  <option value="UNKNOWN">미확인</option>
                  <option value="RESOURCE">자원 부족</option>
                  <option value="NETWORK">네트워크</option>
                  <option value="APPLICATION">애플리케이션</option>
                  <option value="DATABASE">데이터베이스</option>
                  <option value="OPERATION">운영 작업</option>
                </select>
              </label>
              <label>
                담당자 ID
                <input v-model="editForm.assigned_to" class="field" type="number" placeholder="예: 1" />
              </label>
              <div class="time-box">
                <span>감지 {{ formatDate(selectedIncident.detected_at) }}</span>
                <span>해결 {{ formatDate(selectedIncident.resolved_at) }}</span>
              </div>
            </div>
            <button @click="saveIncident" class="btn btn-primary" :disabled="saving">저장</button>
          </div>

          <div class="glass-card">
            <h3>조치 기록 추가</h3>
            <textarea v-model="actionForm.action_note" class="field note-field" placeholder="조치 내용, 원인 분석, 후속 계획을 입력하세요." />
            <div class="form-grid compact">
              <label>
                상태 변경
                <select v-model="actionForm.status_code" class="field">
                  <option value="">변경 없음</option>
                  <option value="OPEN">진행중</option>
                  <option value="IN_PROGRESS">조치중</option>
                  <option value="RESOLVED">해결됨</option>
                  <option value="CLOSED">종료</option>
                </select>
              </label>
              <label>
                원인 변경
                <select v-model="actionForm.cause_code" class="field">
                  <option value="">변경 없음</option>
                  <option value="UNKNOWN">미확인</option>
                  <option value="RESOURCE">자원 부족</option>
                  <option value="NETWORK">네트워크</option>
                  <option value="APPLICATION">애플리케이션</option>
                  <option value="DATABASE">데이터베이스</option>
                  <option value="OPERATION">운영 작업</option>
                </select>
              </label>
              <label>
                담당자 변경
                <input v-model="actionForm.assigned_to" class="field" type="number" placeholder="변경 없음" />
              </label>
            </div>
            <button @click="addAction" class="btn btn-primary" :disabled="saving || !actionForm.action_note.trim()">조치 기록</button>
          </div>

          <div class="glass-card">
            <h3>조치 이력</h3>
            <div v-if="!selectedIncident.actions?.length" class="muted">등록된 조치 이력이 없습니다.</div>
            <div v-else class="timeline">
              <div v-for="action in selectedIncident.actions" :key="action.action_id" class="timeline-item">
                <div class="timeline-time">{{ formatDate(action.action_at) }}</div>
                <div class="timeline-note">{{ action.action_note }}</div>
                <div class="muted">작성자 {{ action.action_user_id ?? '-' }}</div>
              </div>
            </div>
          </div>

          <div class="glass-card">
            <h3>연결 이벤트</h3>
            <div v-if="!selectedIncident.events?.length" class="muted">연결된 이벤트가 없습니다.</div>
            <div v-else class="linked-events">
              <div v-for="evt in selectedIncident.events" :key="evt.event_uid" class="linked-event">
                <span :class="['badge', statusBadge(evt.status_code)]">{{ evt.status_code }}</span>
                <strong>{{ evt.title }}</strong>
                <span class="muted">{{ formatDate(evt.first_occurred_at) }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.loading,
.empty {
  text-align: center;
  padding: 60px;
  color: var(--text-secondary);
}
.incident-layout {
  display: grid;
  grid-template-columns: minmax(320px, 420px) 1fr;
  gap: 24px;
  align-items: start;
}
.list-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.incident-item {
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
}
.incident-item.active {
  border-color: var(--accent-primary);
  background: rgba(59, 130, 246, 0.12);
}
.incident-row,
.incident-meta,
.linked-event {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
}
.incident-meta {
  justify-content: flex-start;
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 10px;
}
.latest-action {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-column {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.form-grid.compact {
  margin-top: 12px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 13px;
}
.field {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.4);
  color: var(--text-primary);
  padding: 10px 12px;
  font: inherit;
}
.note-field {
  min-height: 100px;
  resize: vertical;
}
.time-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
  justify-content: center;
}
.timeline,
.linked-events {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.timeline-item,
.linked-event {
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
}
.timeline-time,
.muted {
  color: var(--text-secondary);
  font-size: 12px;
}
.timeline-note {
  margin: 6px 0;
}
@media (max-width: 980px) {
  .incident-layout {
    grid-template-columns: 1fr;
  }
}
</style>
