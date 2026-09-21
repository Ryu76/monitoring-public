<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import api from '../api'

const ServerPerformanceGauges = defineAsyncComponent(() => import('./ServerPerformanceGauges.vue'))

interface ServerItem {
  server_id: number
  server_name: string
  host_name: string
  mgmt_ip: string
  os_type_code: string
  composite_status: string
}

interface MetricItem {
  metric_code: string
  dimension_key: string
  dimension_value: string
  metric_value: number
  string_value: string | null
  status_code: string | null
  collected_at: string | null
}

interface CheckHistoryItem {
  check_result_id: number
  target_type_code: string
  target_name: string
  metric_code: string
  metric_value: number | null
  string_value: string | null
  status_code: string | null
  collected_at: string | null
  received_at: string | null
}

type CheckTargetType = 'PROCESS' | 'SERVICE' | 'PORT'

interface CheckTargetDraft {
  id: string
  type: CheckTargetType
  value: string
}

interface ServerDetailData {
  server_id: number
  server_name: string
  host_name: string
  mgmt_ip: string
  os_type_code: string
  os_name: string
  os_version: string
  agent_id: number | null
  agent_status: string
  last_heartbeat_at: string | null
  last_collected_at: string | null
  metrics: MetricItem[]
}

const servers = ref<ServerItem[]>([])
const selectedServerId = ref<number | null>(null)
const detail = ref<ServerDetailData | null>(null)
const loading = ref(true)
const savingName = ref(false)
const savingTargets = ref(false)
const historyLoading = ref(false)
const nameSaved = ref('')
const targetSaved = ref('')
const serverName = ref('')
const historyTitle = ref('점검 이력')
const historyItems = ref<CheckHistoryItem[]>([])
const targetItems = ref<CheckTargetDraft[]>([])
const newTargetType = ref<CheckTargetType>('PROCESS')
const newTargetValue = ref('')

const displayName = (server: ServerItem) => server.server_name || server.host_name || server.mgmt_ip
const targetTypeOptions = [
  { value: 'PROCESS' as CheckTargetType, label: '프로세스', hint: '실행 중이어야 하는 프로그램 이름', placeholder: '예: oracle.exe' },
  { value: 'SERVICE' as CheckTargetType, label: '서비스', hint: '운영체제에 등록된 서비스 이름', placeholder: '예: Spooler' },
  { value: 'PORT' as CheckTargetType, label: '포트', hint: '열려 있어야 하는 통신 포트 번호', placeholder: '예: 1521' }
]
const selectedTargetOption = computed(() => targetTypeOptions.find(option => option.value === newTargetType.value) || targetTypeOptions[0])
const makeTargetId = (type: CheckTargetType, value: string, index = Date.now()) => `${type}-${value}-${index}`
const normalizeTargetValue = (type: CheckTargetType, value: string) => {
  const next = value.trim()
  if (!next) return ''
  if (type === 'PORT') {
    const port = Number(next)
    if (!Number.isInteger(port) || port < 1 || port > 65535) return ''
    return String(port)
  }
  return next
}
const targetItemsByType = (type: CheckTargetType) => targetItems.value.filter(item => item.type === type)
const targetCountByType = (type: CheckTargetType) => targetItemsByType(type).length
const addCheckTarget = () => {
  const value = normalizeTargetValue(newTargetType.value, newTargetValue.value)
  if (!value) {
    targetSaved.value = newTargetType.value === 'PORT' ? '포트는 1~65535 사이의 숫자로 입력해주세요.' : '점검할 대상을 입력해주세요.'
    return
  }
  const exists = targetItems.value.some(item => item.type === newTargetType.value && item.value.toLowerCase() === value.toLowerCase())
  if (exists) {
    targetSaved.value = '이미 등록된 점검 대상입니다.'
    return
  }
  targetItems.value.push({ id: makeTargetId(newTargetType.value, value), type: newTargetType.value, value })
  newTargetValue.value = ''
  targetSaved.value = ''
}
const removeCheckTarget = (id: string) => {
  targetItems.value = targetItems.value.filter(item => item.id !== id)
  targetSaved.value = ''
}

const metricGuide: Record<string, { name: string; description: string; good: string; bad: string }> = {
  CPU_USAGE_PCT: {
    name: 'CPU 사용률',
    description: '서버의 두뇌 역할을 하는 CPU가 얼마나 바쁘게 일하고 있는지 보여줍니다.',
    good: '낮거나 적당하면 여유가 있습니다.',
    bad: '오랫동안 80~90% 이상이면 서버가 느려질 수 있습니다.'
  },
  MEM_USAGE_PCT: {
    name: '메모리 사용률',
    description: '프로그램들이 작업 공간인 메모리를 얼마나 쓰고 있는지 보여줍니다.',
    good: '낮거나 적당하면 새 작업을 처리할 여유가 있습니다.',
    bad: '높게 유지되면 프로그램이 느려지거나 멈출 수 있습니다.'
  },
  MEM_AVAILABLE_BYTES: {
    name: '사용 가능한 메모리',
    description: '지금 바로 더 사용할 수 있는 메모리 용량입니다.',
    good: '값이 클수록 여유 공간이 많습니다.',
    bad: '너무 작으면 새 작업을 처리하기 어렵습니다.'
  },
  DISK_USAGE_PCT: {
    name: '디스크 사용률',
    description: '저장 공간이 얼마나 차 있는지 보여줍니다.',
    good: '낮을수록 저장 공간에 여유가 있습니다.',
    bad: '90% 이상이면 로그나 파일 저장에 문제가 생길 수 있습니다.'
  },
  DISK_AVAILABLE_BYTES: {
    name: '남은 디스크 공간',
    description: '파일을 더 저장할 수 있는 남은 저장 공간입니다.',
    good: '값이 클수록 안전합니다.',
    bad: '너무 작으면 서비스가 파일을 쓰지 못할 수 있습니다.'
  },
  NET_BYTES_SENT: {
    name: '네트워크 보낸 양',
    description: '서버가 밖으로 보낸 데이터의 누적량입니다.',
    good: '평소 패턴과 비슷하면 정상입니다.',
    bad: '갑자기 크게 늘면 대량 전송이나 이상 트래픽을 확인해야 합니다.'
  },
  NET_BYTES_RECV: {
    name: '네트워크 받은 양',
    description: '서버가 외부에서 받은 데이터의 누적량입니다.',
    good: '평소 패턴과 비슷하면 정상입니다.',
    bad: '갑자기 크게 늘면 접속 폭주나 이상 트래픽을 확인해야 합니다.'
  },
  PROCESS_CPU_PCT: {
    name: '프로세스 CPU 사용률',
    description: '특정 프로그램이 CPU를 얼마나 쓰고 있는지 보여줍니다.',
    good: '일시적으로 높을 수 있지만 금방 내려오면 괜찮습니다.',
    bad: '계속 높으면 해당 프로그램이 서버를 바쁘게 만들고 있을 수 있습니다.'
  },
  PROCESS_MEM_PCT: {
    name: '프로세스 메모리 사용률',
    description: '특정 프로그램이 메모리를 얼마나 차지하는지 보여줍니다.',
    good: '평소 수준이면 정상입니다.',
    bad: '계속 증가하면 메모리 누수를 의심할 수 있습니다.'
  },
  PROCESS_STATUS: {
    name: '프로세스 실행 상태',
    description: '점검 대상으로 등록한 프로그램이 실행 중인지 확인합니다.',
    good: 'RUNNING이면 실행 중입니다.',
    bad: 'STOPPED이면 꺼져 있어 확인이 필요합니다.'
  },
  PORT_LISTEN: {
    name: '포트 열림 상태',
    description: '서버가 해당 번호의 통신 창구를 열어 두었는지 확인합니다.',
    good: 'LISTENING이면 접속을 받을 준비가 된 상태입니다.',
    bad: 'CLOSED이면 접속을 받을 수 없는 상태입니다.'
  },
  SERVICE_STATUS: {
    name: '서비스 실행 상태',
    description: '운영체제 서비스가 실행 중인지 확인합니다.',
    good: 'running 또는 active이면 정상 실행 중입니다.',
    bad: 'stopped, inactive, unknown이면 확인이 필요합니다.'
  }
}

const fetchServers = async () => {
  try {
    const res = await api.get('/api/v1/servers')
    servers.value = res.data.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchDetail = async () => {
  if (!selectedServerId.value) return
  try {
    const [detailRes, targetRes] = await Promise.all([
      api.get(`/api/v1/servers/${selectedServerId.value}`),
      api.get(`/api/v1/servers/${selectedServerId.value}/check-targets`)
    ])
    detail.value = detailRes.data.data
    serverName.value = detail.value?.server_name || ''
    targetItems.value = [
      ...(targetRes.data.data.processes || []).map((value: string, index: number) => ({ id: makeTargetId('PROCESS', String(value), index), type: 'PROCESS' as CheckTargetType, value: String(value) })),
      ...(targetRes.data.data.services || []).map((value: string, index: number) => ({ id: makeTargetId('SERVICE', String(value), index), type: 'SERVICE' as CheckTargetType, value: String(value) })),
      ...(targetRes.data.data.ports || []).map((value: number | string, index: number) => ({ id: makeTargetId('PORT', String(value), index), type: 'PORT' as CheckTargetType, value: String(value) }))
    ]
    nameSaved.value = ''
    targetSaved.value = ''
    historyItems.value = []
    historyTitle.value = '점검 이력'
  } catch (e) {
    console.error(e)
  }
}

const selectServer = async (id: number) => {
  selectedServerId.value = id
  await fetchDetail()
}

const saveServerName = async () => {
  if (!selectedServerId.value || !serverName.value.trim()) return
  savingName.value = true
  nameSaved.value = ''
  try {
    const res = await api.put(`/api/v1/servers/${selectedServerId.value}`, {
      server_name: serverName.value.trim()
    })
    if (detail.value) detail.value.server_name = res.data.data.server_name
    const target = servers.value.find(s => s.server_id === selectedServerId.value)
    if (target) target.server_name = res.data.data.server_name
    nameSaved.value = '서버 이름이 저장되었습니다.'
  } catch (e) {
    console.error(e)
    nameSaved.value = '서버 이름 저장에 실패했습니다.'
  } finally {
    savingName.value = false
  }
}

const saveCheckTargets = async () => {
  if (!selectedServerId.value) return
  savingTargets.value = true
  targetSaved.value = ''
  try {
    await api.put(`/api/v1/servers/${selectedServerId.value}/check-targets`, {
      processes: targetItems.value.filter(item => item.type === 'PROCESS').map(item => item.value),
      services: targetItems.value.filter(item => item.type === 'SERVICE').map(item => item.value),
      ports: targetItems.value
        .filter(item => item.type === 'PORT')
        .map(item => Number(item.value))
        .filter(value => Number.isInteger(value) && value > 0 && value <= 65535)
    })
    targetSaved.value = '저장되었습니다. 에이전트가 다음 하트비트 응답에서 반영합니다.'
    await fetchDetail()
  } catch (e) {
    console.error(e)
    targetSaved.value = '저장에 실패했습니다.'
  } finally {
    savingTargets.value = false
  }
}

const fetchCheckHistory = async (targetType: string, targetName: string) => {
  if (!selectedServerId.value) return
  historyLoading.value = true
  historyTitle.value = `${targetTypeLabel(targetType)} ${targetName} 이력`
  try {
    const res = await api.get(`/api/v1/servers/${selectedServerId.value}/check-history`, {
      params: { target_type_code: targetType, target_name: targetName, limit: 100 }
    })
    historyItems.value = res.data.data
  } catch (e) {
    console.error(e)
    historyItems.value = []
  } finally {
    historyLoading.value = false
  }
}

const findMetric = (codes: string[]) => detail.value?.metrics.find(m => codes.includes(m.metric_code)) ?? null
const findMetrics = (codes: string[]) => detail.value?.metrics.filter(m => codes.includes(m.metric_code)) ?? []

const cpuMetric = computed(() => findMetric(['SYS_CPU_USAGE', 'CPU_USAGE_PCT', 'CPU_USAGE', 'cpu_usage']))
const memMetric = computed(() => findMetric(['SYS_MEM_USAGE', 'MEM_USAGE_PCT', 'MEM_USAGE', 'mem_usage']))
const diskMetrics = computed(() => findMetrics(['SYS_DISK_USAGE', 'DISK_USAGE_PCT', 'DISK_USAGE', 'disk_usage']))
const diskUsageItems = computed(() => diskMetrics.value.map(d => ({
  name: d.dimension_value || d.dimension_key || '디스크',
  value: Number(d.metric_value ?? 0),
  collected_at: d.collected_at
})).sort((a, b) => b.value - a.value))
const processCpuMetrics = computed(() => findMetrics(['PROCESS_CPU_PCT']).sort((a, b) => b.metric_value - a.metric_value))
const processMemMetrics = computed(() => findMetrics(['PROCESS_MEM_PCT']).sort((a, b) => b.metric_value - a.metric_value))
const processCheckMetrics = computed(() => findMetrics(['PROCESS_STATUS']).sort((a, b) => a.dimension_value.localeCompare(b.dimension_value)))
const portMetrics = computed(() => findMetrics(['PORT_LISTEN']).sort((a, b) => Number(a.dimension_value) - Number(b.dimension_value)))
const serviceMetrics = computed(() => findMetrics(['SERVICE_STATUS']).sort((a, b) => a.dimension_value.localeCompare(b.dimension_value)))
const emptyMetrics = computed<MetricItem[]>(() => [])

const diskStatusLabel = (value: number) => {
  if (value >= 90) return '위험'
  if (value >= 80) return '주의'
  if (value >= 60) return '보통'
  return '여유'
}
const diskStatusClass = (value: number) => {
  if (value >= 90) return 'badge-fatal'
  if (value >= 80) return 'badge-warning'
  return 'badge-normal'
}
const diskBarClass = (value: number) => {
  if (value >= 90) return 'disk-fill danger'
  if (value >= 80) return 'disk-fill warning'
  return 'disk-fill'
}

const formatDate = (value: string | null) => value?.replace('T', ' ').slice(0, 19) ?? '-'
const formatPercent = (value: number) => `${Number(value ?? 0).toFixed(1)}%`
const formatBytes = (value: number) => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let next = Number(value ?? 0)
  let unit = 0
  while (next >= 1024 && unit < units.length - 1) {
    next /= 1024
    unit += 1
  }
  return `${next.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}
const metricDisplayValue = (m: MetricItem) => {
  if (m.metric_code.endsWith('_BYTES')) return formatBytes(m.metric_value)
  if (m.metric_code.endsWith('_PCT')) return formatPercent(m.metric_value)
  if (['PORT_LISTEN', 'SERVICE_STATUS', 'PROCESS_STATUS'].includes(m.metric_code)) return m.string_value || (m.metric_value === 1 ? '정상' : '경고')
  return m.metric_value
}
const metricGuideFor = (m: MetricItem) => metricGuide[m.metric_code] || {
  name: m.metric_code,
  description: '서버에서 수집한 원본 지표입니다.',
  good: '평소 값과 비교해서 보면 됩니다.',
  bad: '갑자기 크게 변하면 확인이 필요합니다.'
}
const metricTargetLabel = (m: MetricItem) => {
  if (!m.dimension_value || m.dimension_value === '-') return '서버 전체'
  if (m.dimension_key === 'path') return `경로 ${m.dimension_value}`
  if (m.dimension_key === 'process') return `프로그램 ${m.dimension_value}`
  if (m.dimension_key === 'service') return `서비스 ${m.dimension_value}`
  if (m.dimension_key === 'port') return `포트 ${m.dimension_value}`
  return m.dimension_value
}
const metricMeaning = (m: MetricItem) => {
  const guide = metricGuideFor(m)
  if (['PORT_LISTEN', 'SERVICE_STATUS', 'PROCESS_STATUS'].includes(m.metric_code)) {
    return m.metric_value === 1 ? guide.good : guide.bad
  }
  if (m.metric_code.endsWith('_PCT')) {
    if (m.metric_value >= 90) return '매우 높은 상태입니다. 바로 확인하는 것이 좋습니다.'
    if (m.metric_value >= 80) return '높은 편입니다. 지속되는지 확인하세요.'
    if (m.metric_value >= 60) return '보통보다 조금 바쁜 상태입니다.'
    return '여유가 있는 상태입니다.'
  }
  if (m.metric_code.endsWith('_BYTES')) return '용량 값입니다. 남은 공간이나 누적 전송량을 확인할 때 봅니다.'
  return guide.good
}
const metricTone = (m: MetricItem) => {
  if (['PORT_LISTEN', 'SERVICE_STATUS', 'PROCESS_STATUS'].includes(m.metric_code)) return healthBadge(m.string_value, m.metric_value)
  if (m.metric_code.endsWith('_PCT') && m.metric_value >= 90) return 'badge-fatal'
  if (m.metric_code.endsWith('_PCT') && m.metric_value >= 80) return 'badge-warning'
  return 'badge-normal'
}
const healthBadge = (value: string | null | undefined, metricValue?: number) => {
  const normalized = (value || '').toUpperCase()
  if (['NORMAL', 'OK', 'LISTENING', 'RUNNING', 'ACTIVE'].includes(normalized) || metricValue === 1) return 'badge-normal'
  if (normalized === 'UNKNOWN') return 'badge-unknown'
  return 'badge-warning'
}
const targetTypeLabel = (value: string) => {
  if (value === 'PROCESS') return '프로세스'
  if (value === 'SERVICE') return '서비스'
  if (value === 'PORT') return '포트'
  return value
}

onMounted(fetchServers)
</script>

<template>
  <div class="container server-detail-page animate-fade-in">
    <h1 style="margin-bottom: 4px;">서버 상세</h1>
    <p>서버 표시 이름, 성능 지표, 점검 대상과 조회 이력을 관리합니다.</p>

    <div v-if="loading" style="text-align: center; padding: 80px; color: var(--text-secondary);">불러오는 중...</div>

    <template v-if="!loading">
      <div class="server-flow">
        <section class="glass-card server-list-section">
          <div class="server-list-head">
            <div>
              <h3>서버 목록</h3>
              <p class="section-subtitle">상세정보를 확인할 서버를 선택하세요.</p>
            </div>
            <span>{{ servers.length }}개</span>
          </div>
          <div class="server-list-buttons">
        <button
          v-for="s in servers" :key="s.server_id"
          @click="selectServer(s.server_id)"
          :class="['server-list-item', selectedServerId === s.server_id ? 'active' : '']"
          type="button"
        >
          <span>{{ displayName(s) }}</span>
          <small>{{ s.mgmt_ip }}</small>
        </button>
          </div>
        </section>

        <section class="server-detail-panel">

      <div class="detail-section-head">
        <h3>상세정보</h3>
        <p class="section-subtitle">선택한 서버의 상태, 점검 대상, 수집 지표를 확인합니다.</p>
      </div>

      <div v-if="!detail" class="empty-detail">
        서버를 선택하세요.
      </div>

      <template v-else>
        <div class="glass-card server-name-card">
          <div>
            <h3>서버 표시 이름</h3>
            <p>{{ detail.host_name }} / {{ detail.mgmt_ip }}</p>
          </div>
          <div class="name-editor">
            <input v-model="serverName" type="text" maxlength="100" placeholder="서버 이름 입력" />
            <button @click="saveServerName" class="btn btn-primary" :disabled="savingName || !serverName.trim()">
              {{ savingName ? '저장 중...' : '저장' }}
            </button>
          </div>
          <p v-if="nameSaved" class="save-message">{{ nameSaved }}</p>
        </div>

        <div class="glass-card server-info">
          <div><span class="info-label">표시 이름</span><span class="info-value">{{ detail.server_name }}</span></div>
          <div><span class="info-label">호스트</span><span class="info-value">{{ detail.host_name }}</span></div>
          <div><span class="info-label">IP</span><span class="info-value">{{ detail.mgmt_ip }}</span></div>
          <div><span class="info-label">OS</span><span class="info-value">{{ detail.os_name }} {{ detail.os_version }}</span></div>
          <div><span class="info-label">에이전트</span><span :class="['badge', healthBadge(detail.agent_status)]">{{ detail.agent_status }}</span></div>
          <div><span class="info-label">마지막 하트비트</span><span class="info-value">{{ formatDate(detail.last_heartbeat_at) }}</span></div>
          <div><span class="info-label">마지막 수집</span><span class="info-value">{{ formatDate(detail.last_collected_at) }}</span></div>
        </div>

        <div class="glass-card check-target-card">
          <div class="section-header">
            <h3>점검 대상 설정</h3>
            <button @click="saveCheckTargets" class="btn btn-primary" :disabled="savingTargets">
              {{ savingTargets ? '저장 중...' : '저장' }}
            </button>
          </div>
          <div class="target-builder">
            <div class="target-type-tabs">
              <button
                v-for="option in targetTypeOptions"
                :key="option.value"
                type="button"
                :class="['target-type-button', newTargetType === option.value ? 'active' : '']"
                @click="newTargetType = option.value"
              >
                <span>{{ option.label }}</span>
                <small>{{ targetCountByType(option.value) }}개</small>
              </button>
            </div>

            <div class="target-input-row">
              <div class="target-input-copy">
                <strong>{{ selectedTargetOption.label }}</strong>
                <span>{{ selectedTargetOption.hint }}</span>
              </div>
              <input
                v-model="newTargetValue"
                :placeholder="selectedTargetOption.placeholder"
                @keydown.enter.prevent="addCheckTarget"
              />
              <button type="button" class="btn btn-outline" @click="addCheckTarget">추가</button>
            </div>
          </div>

          <div class="target-list-grid">
            <div v-for="option in targetTypeOptions" :key="`list-${option.value}`" class="target-list-panel">
              <div class="target-list-title">
                <span>{{ option.label }}</span>
                <small>{{ option.hint }}</small>
              </div>
              <div v-if="targetItemsByType(option.value).length === 0" class="target-empty">등록된 대상이 없습니다.</div>
              <div v-else class="target-chip-list">
                <button
                  v-for="item in targetItemsByType(option.value)"
                  :key="item.id"
                  type="button"
                  class="target-chip"
                  @click="removeCheckTarget(item.id)"
                  :title="`${item.value} 삭제`"
                >
                  <span>{{ item.value }}</span>
                  <span aria-hidden="true">×</span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="false" class="target-grid">
            <label>
              <span>프로세스</span>
              <textarea placeholder="nginx&#10;python.exe&#10;java"></textarea>
            </label>
            <label>
              <span>서비스</span>
              <textarea placeholder="nginx&#10;postgresql&#10;Spooler"></textarea>
            </label>
            <label>
              <span>포트</span>
              <textarea placeholder="80&#10;443&#10;1521"></textarea>
            </label>
          </div>
          <p v-if="targetSaved" class="save-message">{{ targetSaved }}</p>
        </div>

        <ServerPerformanceGauges
          v-if="detail"
          :cpu-value="cpuMetric?.metric_value ?? 0"
          :memory-value="memMetric?.metric_value ?? 0"
        />

        <div class="glass-card disk-card" v-if="diskUsageItems.length > 0">
          <div class="section-header">
            <div>
              <h3>디스크 사용률</h3>
              <p class="section-subtitle">저장 공간이 얼마나 차 있는지 드라이브별로 보여줍니다.</p>
            </div>
            <span class="history-count">{{ diskUsageItems.length }}개 드라이브</span>
          </div>
          <div class="disk-grid">
            <div v-for="disk in diskUsageItems" :key="disk.name" class="disk-item">
              <div class="disk-topline">
                <div>
                  <div class="disk-name">{{ disk.name }}</div>
                  <div class="disk-hint">{{ disk.value >= 80 ? '공간 정리가 필요할 수 있습니다.' : '저장 공간에 여유가 있습니다.' }}</div>
                </div>
                <span :class="['badge', diskStatusClass(disk.value)]">{{ diskStatusLabel(disk.value) }}</span>
              </div>
              <div class="disk-meter" aria-hidden="true">
                <div :class="diskBarClass(disk.value)" :style="{ width: `${Math.min(100, Math.max(0, disk.value))}%` }"></div>
              </div>
              <div class="disk-footer">
                <span>{{ formatPercent(disk.value) }} 사용 중</span>
                <span>{{ formatDate(disk.collected_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="metric-grid">
          <div class="glass-card" v-if="processCheckMetrics.length > 0">
            <h3>프로세스 점검</h3>
            <div class="metric-list">
              <div v-for="m in processCheckMetrics" :key="`check-${m.dimension_value}`" class="metric-row">
                <span class="metric-name">{{ m.dimension_value }}</span>
                <span :class="['badge', healthBadge(m.string_value, m.metric_value)]">{{ m.string_value || '-' }}</span>
                <button class="btn btn-outline mini-btn" @click="fetchCheckHistory('PROCESS', m.dimension_value)">이력</button>
              </div>
            </div>
          </div>

          <div class="glass-card" v-if="serviceMetrics.length > 0">
            <h3>서비스 점검</h3>
            <div class="metric-list">
              <div v-for="m in serviceMetrics" :key="`service-${m.dimension_value}`" class="metric-row">
                <span class="metric-name">{{ m.dimension_value }}</span>
                <span :class="['badge', healthBadge(m.string_value, m.metric_value)]">{{ m.string_value || '-' }}</span>
                <button class="btn btn-outline mini-btn" @click="fetchCheckHistory('SERVICE', m.dimension_value)">이력</button>
              </div>
            </div>
          </div>

          <div class="glass-card" v-if="portMetrics.length > 0">
            <h3>포트 점검</h3>
            <div class="metric-list">
              <div v-for="m in portMetrics" :key="`port-${m.dimension_value}`" class="metric-row">
                <span class="metric-name">포트 {{ m.dimension_value }}</span>
                <span :class="['badge', healthBadge(m.string_value, m.metric_value)]">{{ m.string_value || '-' }}</span>
                <button class="btn btn-outline mini-btn" @click="fetchCheckHistory('PORT', m.dimension_value)">이력</button>
              </div>
            </div>
          </div>
        </div>

        <div class="glass-card history-card">
          <div class="section-header">
            <h3>{{ historyTitle }}</h3>
            <span class="history-count">{{ historyLoading ? '조회 중...' : `${historyItems.length}건` }}</span>
          </div>
          <div v-if="historyItems.length === 0" class="empty-history">
            조회된 점검 이력이 없습니다.
          </div>
          <table v-else style="width: 100%; text-align: left; border-collapse: collapse;">
            <thead>
              <tr style="border-bottom: 1px solid var(--surface-border);">
                <th class="th">대상</th>
                <th class="th">상태</th>
                <th class="th">값</th>
                <th class="th">수집 시각</th>
                <th class="th">수신 시각</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in historyItems" :key="item.check_result_id" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td class="td">{{ targetTypeLabel(item.target_type_code) }} {{ item.target_name }}</td>
                <td class="td"><span :class="['badge', healthBadge(item.string_value, item.metric_value ?? undefined)]">{{ item.string_value || item.status_code || '-' }}</span></td>
                <td class="td">{{ item.metric_value }}</td>
                <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ formatDate(item.collected_at) }}</td>
                <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ formatDate(item.received_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="metric-grid">
          <div class="glass-card" v-if="processCpuMetrics.length > 0">
            <h3>CPU 사용 상위 프로세스</h3>
            <div class="metric-list">
              <div v-for="m in processCpuMetrics" :key="`cpu-${m.dimension_value}`" class="metric-row">
                <span class="metric-name">{{ m.dimension_value }}</span>
                <span class="metric-value">{{ formatPercent(m.metric_value) }}</span>
              </div>
            </div>
          </div>

          <div class="glass-card" v-if="processMemMetrics.length > 0">
            <h3>메모리 사용 상위 프로세스</h3>
            <div class="metric-list">
              <div v-for="m in processMemMetrics" :key="`mem-${m.dimension_value}`" class="metric-row">
                <span class="metric-name">{{ m.dimension_value }}</span>
                <span class="metric-value">{{ formatPercent(m.metric_value) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="glass-card metric-guide-card" v-if="detail.metrics.length > 0">
          <div class="section-header">
            <div>
              <h3>전체 지표</h3>
              <p class="section-subtitle">현재 서버에서 수집된 값을 쉽게 풀어서 보여줍니다.</p>
            </div>
            <span class="history-count">{{ detail.metrics.length }}개</span>
          </div>
          <div class="friendly-metric-grid">
            <article v-for="(m, i) in detail.metrics" :key="`friendly-card-${i}`" class="friendly-metric-card">
              <div class="friendly-metric-head">
                <div class="friendly-metric-name">
                  <div class="metric-title">{{ metricGuideFor(m).name }}</div>
                  <div class="metric-code">{{ m.metric_code }}</div>
                </div>
                <span :class="['badge', metricTone(m)]">{{ metricDisplayValue(m) }}</span>
              </div>
              <p class="friendly-metric-desc">{{ metricGuideFor(m).description }}</p>
              <div class="friendly-metric-meaning">{{ metricMeaning(m) }}</div>
              <div class="friendly-metric-meta">
                <span>{{ metricTargetLabel(m) }}</span>
                <span>{{ formatDate(m.collected_at) }}</span>
              </div>
            </article>
          </div>
        </div>

        <div class="glass-card" style="margin-top: 24px;" v-if="false">
          <h3 style="margin-bottom: 12px;">전체 지표 쉬운 설명</h3>
          <table style="width: 100%; text-align: left; border-collapse: collapse;">
            <thead>
              <tr style="border-bottom: 1px solid var(--surface-border);">
                <th class="th">이름</th>
                <th class="th">무엇을 뜻하나</th>
                <th class="th">현재 값</th>
                <th class="th">해석</th>
                <th class="th">수집 시각</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, i) in emptyMetrics" :key="`friendly-${i}`" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td class="td">
                  <div class="metric-title">{{ metricGuideFor(m).name }}</div>
                  <div class="metric-code">{{ m.metric_code }}</div>
                </td>
                <td class="td">
                  <div>{{ metricGuideFor(m).description }}</div>
                  <div class="metric-code">{{ metricTargetLabel(m) }}</div>
                </td>
                <td class="td"><span :class="['badge', metricTone(m)]">{{ metricDisplayValue(m) }}</span></td>
                <td class="td" style="color: var(--text-secondary);">{{ metricMeaning(m) }}</td>
                <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ formatDate(m.collected_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="glass-card raw-metric-card" style="margin-top: 24px;" v-if="false">
          <h3 style="margin-bottom: 12px;">전체 지표</h3>
          <table style="width: 100%; text-align: left; border-collapse: collapse;">
            <thead>
              <tr style="border-bottom: 1px solid var(--surface-border);">
                <th class="th">지표 코드</th>
                <th class="th">대상</th>
                <th class="th">값</th>
                <th class="th">수집 시각</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, i) in emptyMetrics" :key="i" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td class="td" style="font-weight: 500;">{{ m.metric_code }}</td>
                <td class="td" style="color: var(--text-secondary);">{{ m.dimension_value || '-' }}</td>
                <td class="td">{{ metricDisplayValue(m) }}</td>
                <td class="td" style="color: var(--text-secondary); font-size: 13px;">{{ formatDate(m.collected_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
          </template>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.server-detail-page {
  width: min(100%, 1440px);
}
.server-flow {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.server-list-section {
  margin-top: 20px;
}
.server-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  color: var(--text-primary);
}
.server-list-head h3 {
  margin: 0;
}
.server-list-head span {
  color: var(--text-secondary);
  font-size: 12px;
}
.server-list-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.server-list-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}
.server-list-item.active {
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.18);
}
.server-list-item span,
.server-list-item small {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.server-list-item small {
  color: var(--text-secondary);
  font-size: 12px;
}
.server-detail-panel {
  min-width: 0;
}
.detail-section-head {
  margin-bottom: 16px;
}
.detail-section-head h3 {
  margin: 0;
}
.empty-detail {
  border: 1px dashed var(--surface-border);
  border-radius: 8px;
  padding: 40px;
  color: var(--text-secondary);
  text-align: center;
}
.server-name-card,
.check-target-card,
.history-card {
  margin-bottom: 24px;
}
.server-name-card h3,
.section-header h3 {
  margin: 0;
}
.glass-card h3 {
  line-height: 1.35;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.server-name-card p {
  margin: 4px 0 0;
  color: var(--text-secondary);
}
.name-editor {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.name-editor input {
  flex: 1;
  min-width: 0;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  outline: none;
}
.server-info {
  margin-bottom: 24px;
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}
.info-label {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-secondary);
  display: block;
  letter-spacing: 1px;
  margin-bottom: 4px;
}
.info-value {
  font-weight: 600;
  font-size: 15px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.section-subtitle {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.disk-card {
  margin-bottom: 24px;
}
.disk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}
.disk-item {
  padding: 16px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
}
.disk-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.disk-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
}
.disk-hint {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}
.disk-meter {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}
.disk-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #10b981, #22c55e);
}
.disk-fill.warning {
  background: linear-gradient(90deg, #f59e0b, #f97316);
}
.disk-fill.danger {
  background: linear-gradient(90deg, #ef4444, #f43f5e);
}
.disk-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}
.target-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.target-grid label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}
.target-grid textarea {
  min-height: 110px;
  resize: vertical;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  outline: none;
  font-family: inherit;
}
.target-builder {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 16px;
}
.target-type-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.target-type-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 52px;
  padding: 12px 14px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}
.target-type-button.active {
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.16);
  color: var(--text-primary);
}
.target-type-button span {
  font-weight: 700;
}
.target-type-button small {
  color: var(--text-secondary);
  font-size: 12px;
}
.target-input-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
}
.target-input-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.target-input-copy strong {
  color: var(--text-primary);
}
.target-input-copy span {
  color: var(--text-secondary);
  font-size: 12px;
}
.target-input-row input {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  outline: none;
}
.target-input-row input:focus {
  border-color: var(--accent-primary);
}
.target-list-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}
.target-list-panel {
  min-height: 116px;
  padding: 14px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.34);
}
.target-list-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}
.target-list-title span {
  color: var(--text-primary);
  font-weight: 700;
}
.target-list-title small,
.target-empty {
  color: var(--text-secondary);
  font-size: 12px;
}
.target-empty {
  padding: 12px 0;
}
.target-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.target-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  padding: 7px 10px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  cursor: pointer;
}
.target-chip span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.target-chip:hover {
  border-color: var(--danger);
  color: var(--danger);
}
.save-message,
.history-count,
.empty-history {
  color: var(--text-secondary);
  font-size: 13px;
}
.save-message {
  margin: 12px 0 0;
}
.empty-history {
  padding: 20px 0;
  text-align: center;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  margin-top: 24px;
}
.metric-guide-card {
  margin-top: 24px;
}
.friendly-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}
.friendly-metric-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--surface-border);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.32);
}
.friendly-metric-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}
.friendly-metric-name {
  min-width: 0;
}
.friendly-metric-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.friendly-metric-meaning {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.045);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  word-break: keep-all;
}
.friendly-metric-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}
.th {
  padding: 12px 8px;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 13px;
}
.td {
  padding: 12px 8px;
}
.metric-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.metric-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  min-height: 28px;
}
.metric-name {
  color: var(--text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.metric-value {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 13px;
}
.metric-title {
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
  line-height: 1.35;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.metric-code {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.4;
  word-break: break-word;
}
.mini-btn {
  padding: 5px 9px;
  font-size: 12px;
}
@media (max-width: 760px) {
  .server-detail-page {
    width: 100%;
  }
  .server-flow {
    gap: 18px;
  }
  .server-list-head {
    flex-direction: column;
    gap: 8px;
  }
  .server-list-buttons {
    grid-template-columns: 1fr;
  }
  .server-info {
    gap: 16px;
  }
  .server-info > div {
    flex: 1 1 180px;
    min-width: 0;
  }
  .history-card {
    overflow-x: auto;
  }
  .history-card table {
    min-width: 640px;
  }
  .metric-grid,
  .friendly-metric-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .section-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .target-type-tabs,
  .target-input-row {
    grid-template-columns: 1fr;
  }
  .name-editor {
    flex-direction: column;
  }
  .name-editor .btn {
    width: 100%;
  }
}
@media (max-width: 520px) {
  .server-detail-page {
    padding-left: 0;
    padding-right: 0;
  }
  .server-list-head h3,
  .detail-section-head h3 {
    font-size: 20px;
  }
  .server-info {
    flex-direction: column;
    gap: 12px;
  }
  .server-info > div {
    flex: 1 1 auto;
  }
  .target-type-button {
    min-height: 46px;
  }
  .target-input-row {
    padding: 12px;
  }
  .target-input-row .btn {
    width: 100%;
  }
  .server-list-section,
  .friendly-metric-card,
  .target-list-panel,
  .disk-item {
    padding: 12px;
  }
  .target-chip {
    width: 100%;
    justify-content: space-between;
  }
  .disk-topline,
  .disk-footer {
    flex-direction: column;
    align-items: flex-start;
  }
  .friendly-metric-head {
    grid-template-columns: 1fr;
  }
  .friendly-metric-head .badge {
    width: fit-content;
  }
  .friendly-metric-meta {
    align-items: flex-start;
    flex-direction: column;
  }
  .metric-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .metric-row .mini-btn {
    grid-column: 1 / -1;
    width: 100%;
  }
}
</style>
