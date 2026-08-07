<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { unwrapResponse, formatHourlyBonus } from '../provider'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
  allowRefresh: {
    type: Boolean,
    default: true,
  },
})

const loading = ref(false)
const metrics = ref([])
let timer = null

const validMetrics = computed(() =>
  metrics.value.filter(m => m.hourly_bonus !== null && m.hourly_bonus !== undefined)
)
const topMetrics = computed(() =>
  [...validMetrics.value].sort((a, b) => (b.hourly_bonus || 0) - (a.hourly_bonus || 0)).slice(0, 8)
)
const summary = computed(() => {
  const list = metrics.value
  const valid = validMetrics.value
  return {
    sites: list.length,
    bonus: list.reduce((sum, m) => sum + (m.bonus || 0), 0),
    seeding: list.reduce((sum, m) => sum + (m.seeding || 0), 0),
    hourly: valid.reduce((sum, m) => sum + (m.hourly_bonus || 0), 0),
    validCount: valid.length,
  }
})

async function loadStatus() {
  if (!props.allowRefresh) return
  loading.value = true
  try {
    const response = await props.api.get('plugin/SiteBonusMonitor/metrics')
    metrics.value = unwrapResponse(response) || []
  } catch (err) {
    // 静默失败
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatus()
  timer = window.setInterval(loadStatus, 60000)
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})
</script>

<template>
  <div class="sitebonus-dashboard">
    <div v-if="summary.sites > 0" class="d-flex flex-column" style="gap: 16px">
      <!-- Top 站点 -->
      <div>
        <div class="text-caption text-medium-emphasis mb-2">时魔 Top 站点</div>
        <VList density="compact" v-if="topMetrics.length">
          <VListItem v-for="m in topMetrics" :key="m.site_id">
            <VListItemTitle>{{ m.site_name }}</VListItemTitle>
            <VListItemSubtitle>魔力 {{ m.bonus.toFixed(2) }} · 做种 {{ m.seeding }}</VListItemSubtitle>
            <template #append>
              <VChip
                size="small"
                :color="(m.hourly_bonus || 0) >= 0 ? 'primary' : 'grey'"
                variant="tonal"
              >
                {{ formatHourlyBonus(m.hourly_bonus) }} /h
              </VChip>
            </template>
          </VListItem>
        </VList>
        <div v-else class="text-caption text-medium-emphasis">暂无 24h 内有效数据</div>
      </div>

      <VDivider />

      <!-- 汇总数字 -->
      <div class="d-flex flex-wrap align-stretch" style="gap: 12px">
        <div class="metric-cell">
          <div class="text-caption text-medium-emphasis">总魔力值</div>
          <div class="text-h6 text-primary mt-1">{{ summary.bonus.toFixed(2) }}</div>
        </div>
        <div class="metric-cell">
          <div class="text-caption text-medium-emphasis">总做种</div>
          <div class="text-h6 text-primary mt-1">{{ summary.seeding }}</div>
        </div>
        <div class="metric-cell">
          <div class="text-caption text-medium-emphasis">总时魔</div>
          <div class="text-h6 text-primary mt-1">
            {{ summary.hourly >= 0 ? '+' : '' }}{{ summary.hourly.toFixed(4) }}
          </div>
        </div>
        <div class="metric-cell">
          <div class="text-caption text-medium-emphasis">有效站点</div>
          <div class="text-h6 text-primary mt-1">{{ summary.validCount }} / {{ summary.sites }}</div>
        </div>
      </div>
    </div>
    <div v-else-if="!loading" class="text-caption text-medium-emphasis">
      暂无站点数据，等待 MoviePilot 采集
    </div>
    <div v-else class="text-caption text-medium-emphasis">加载中...</div>
  </div>
</template>

<style scoped>
.sitebonus-dashboard {
  padding: 8px 0;
}
.metric-cell {
  min-width: 96px;
  padding: 4px 12px;
  border-radius: 6px;
  background: rgba(var(--v-theme-primary), 0.06);
  display: flex;
  flex-direction: column;
  flex: 1 1 96px;
}
</style>