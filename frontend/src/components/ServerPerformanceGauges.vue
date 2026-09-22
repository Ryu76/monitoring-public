<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, GaugeChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const props = defineProps<{
  cpuValue: number
  memoryValue: number
}>()

const gaugeOption = (title: string, value: number, color: string) => ({
  series: [{
    type: 'gauge',
    startAngle: 220,
    endAngle: -40,
    min: 0,
    max: 100,
    radius: '90%',
    progress: { show: true, width: 14, roundCap: true, itemStyle: { color } },
    pointer: { show: false },
    axisLine: { lineStyle: { width: 14, color: [[1, 'rgba(255,255,255,0.08)']] } },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    title: { show: true, offsetCenter: [0, '70%'], fontSize: 13, color: '#94a3b8' },
    detail: {
      valueAnimation: true,
      fontSize: 28,
      fontWeight: 'bold',
      color: '#f8fafc',
      formatter: '{value}%',
      offsetCenter: [0, '30%']
    },
    data: [{ value, name: title }]
  }],
  backgroundColor: 'transparent'
})

const cpuGauge = computed(() => gaugeOption('CPU', props.cpuValue, '#3b82f6'))
const memGauge = computed(() => gaugeOption('메모리', props.memoryValue, '#14b8a6'))
</script>

<template>
  <div class="gauge-grid">
    <div class="glass-card chart-card">
      <VChart :option="cpuGauge" autoresize style="width: 100%; height: 100%;" />
    </div>
    <div class="glass-card chart-card">
      <VChart :option="memGauge" autoresize style="width: 100%; height: 100%;" />
    </div>
  </div>
</template>

<style scoped>
.gauge-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}
.chart-card {
  height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
}
@media (max-width: 760px) {
  .gauge-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .chart-card {
    height: 230px;
  }
}
</style>
