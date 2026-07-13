<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../api'

interface AgentItem {
  agent_id: number
  agent_uid: string
  server_id: number
  host_name: string | null
  mgmt_ip: string | null
  status_code: string
  agent_version: string
  agent_status: string
  last_heartbeat_at: string | null
}

const agents = ref<AgentItem[]>([])
const loading = ref(true)
const actionLoading = ref<number | null>(null)

const fetchAgents = async () => {
  loading.value = true
  try {
    const res = await api.get('/api/v1/agents')
    agents.value = res.data.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const approveAgent = async (id: number) => {
  actionLoading.value = id
  try {
    await api.put(`/api/v1/agents/${id}/approve`)
    await fetchAgents()
  } catch (e) {
    console.error(e)
  } finally {
    actionLoading.value = null
  }
}

const revokeAgent = async (id: number) => {
  actionLoading.value = id
  try {
    await api.put(`/api/v1/agents/${id}/revoke`)
    await fetchAgents()
  } catch (e) {
    console.error(e)
  } finally {
    actionLoading.value = null
  }
}

const statusBadge = (status: string) => {
  switch (status) {
    case 'APPROVED': return 'badge-normal'
    case 'PENDING': return 'badge-warning'
    default: return 'badge-fatal'
  }
}

const heartbeatBadge = (status: string) => {
  switch (status) {
    case 'NORMAL': return 'badge-normal'
    case 'OFFLINE': return 'badge-fatal'
    default: return 'badge-unknown'
  }
}

onMounted(fetchAgents)
</script>

<template>
  <div class="container animate-fade-in">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <div>
        <h1 style="margin-bottom: 4px;">에이전트 관리</h1>
        <p style="margin: 0;">모니터링 에이전트 승인 상태를 관리합니다.</p>
      </div>
      <button @click="fetchAgents" class="btn btn-outline">새로고침</button>
    </div>

    <div v-if="loading" style="text-align: center; padding: 80px; color: var(--text-secondary);">불러오는 중...</div>

    <div v-else-if="agents.length === 0" class="glass-card" style="text-align: center; padding: 60px; color: var(--text-secondary);">
      등록된 에이전트가 없습니다.
    </div>

    <div v-else class="glass-card">
      <table style="width: 100%; text-align: left; border-collapse: collapse;">
        <thead>
          <tr style="border-bottom: 1px solid var(--surface-border);">
            <th class="th">호스트명</th>
            <th class="th">IP 주소</th>
            <th class="th">버전</th>
            <th class="th">승인 상태</th>
            <th class="th">하트비트</th>
            <th class="th">마지막 확인</th>
            <th class="th">조치</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="agent in agents" :key="agent.agent_id" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
            <td class="td" style="font-weight: 500;">{{ agent.host_name || '-' }}</td>
            <td class="td" style="color: var(--text-secondary);">{{ agent.mgmt_ip || '-' }}</td>
            <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ agent.agent_version || '-' }}</td>
            <td class="td">
              <span :class="['badge', statusBadge(agent.status_code)]">{{ agent.status_code }}</span>
            </td>
            <td class="td">
              <span :class="['badge', heartbeatBadge(agent.agent_status)]">{{ agent.agent_status }}</span>
            </td>
            <td class="td" style="color: var(--text-secondary); font-size: 13px;">
              {{ agent.last_heartbeat_at?.replace('T', ' ').slice(0, 19) ?? '없음' }}
            </td>
            <td class="td">
              <div style="display: flex; gap: 8px;">
                <button
                  v-if="agent.status_code !== 'APPROVED'"
                  @click="approveAgent(agent.agent_id)"
                  class="btn btn-success"
                  style="padding: 6px 12px; font-size: 12px;"
                  :disabled="actionLoading === agent.agent_id"
                >승인</button>
                <button
                  v-if="agent.status_code === 'APPROVED'"
                  @click="revokeAgent(agent.agent_id)"
                  class="btn btn-outline"
                  style="padding: 6px 12px; font-size: 12px;"
                  :disabled="actionLoading === agent.agent_id"
                >차단</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.th {
  padding: 14px 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.td {
  padding: 14px 8px;
}
</style>
