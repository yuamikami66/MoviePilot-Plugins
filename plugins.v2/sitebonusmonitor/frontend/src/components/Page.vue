<script setup>
import { computed, onMounted, ref } from 'vue'
import { unwrapResponse, formatHourlyBonus, formatTb } from '../provider'

const props = defineProps({
  api: {
    type: Object,
    default: () => ({}),
  },
})
const emit = defineEmits(['close'])

const loading = ref(false)
const error = ref('')
const metrics = ref([])
const lastUpdated = ref('')
const sortKey = ref(null)
const sortDir = ref('asc')

const testSending = ref(false)
const testMessage = ref('')

const columns = [
  { key: 'site_name', label: '站点', align: 'start', getter: r => r.site_name || '' },
  { key: 'username', label: '用户', align: 'start', getter: r => r.username || '' },
  { key: 'user_level', label: '等级', align: 'start', getter: r => r.user_level || '' },
  { key: 'bonus', label: '魔力值', align: 'end', getter: r => r.bonus || 0 },
  { key: 'seeding', label: '做种', align: 'end', getter: r => r.seeding || 0 },
  { key: 'hourly_bonus', label: '时魔', align: 'end', getter: r => (r.hourly_bonus ?? -Infinity) },
  { key: 'upload_gb', label: '上传', align: 'end', getter: r => r.upload_gb || 0 },
  { key: 'download_gb', label: '下载', align: 'end', getter: r => r.download_gb || 0 },
  { key: 'ratio', label: '分享率', align: 'end', getter: r => r.ratio || 0 },
  { key: 'window_hours', label: '窗口(h)', align: 'end', getter: r => r.window_hours || 0 },
  { key: 'updated_at', label: '更新时间', align: 'start', getter: r => r.updated_at || '' },
]

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

function sortIcon(key) {
  if (sortKey.value !== key) return 'mdi-unfold-more-horizontal'
  return sortDir.value === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down'
}

async function loadMetrics() {
  loading.value = true
  error.value = ''
  try {
    const response = await props.api.get('plugin/SiteBonusMonitor/metrics')
    metrics.value = unwrapResponse(response) || []
    lastUpdated.value = new Date().toLocaleString('zh-CN', { hour12: false })
  } catch (err) {
    error.value = err?.message || '加载站点数据失败'
  } finally {
    loading.value = false
  }
}

async function sendTestNotification() {
  if (!props.api || typeof props.api.post !== 'function') {
    testMessage.value = 'API 不可用：插件上下文未注入 api'
    return
  }
  testSending.value = true
  testMessage.value = ''
  try {
    const response = await props.api.post('plugin/SiteBonusMonitor/test', {})
    const ok = response && (response.success === true || response.data === undefined)
    if (ok) {
      testMessage.value = '已发送测试通知'
    } else {
      testMessage.value = response?.message || response?.data?.message || '发送失败'
    }
  } catch (err) {
    testMessage.value = err?.message || '发送失败'
  } finally {
    testSending.value = false
  }
}

const validMetrics = computed(() => metrics.value.filter(m => m.hourly_bonus !== null && m.hourly_bonus !== undefined))
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

const sortedMetrics = computed(() => {
  if (!sortKey.value) return metrics.value
  const col = columns.find(c => c.key === sortKey.value)
  if (!col) return metrics.value
  const getter = col.getter
  const list = [...metrics.value]
  list.sort((a, b) => {
    const va = getter(a)
    const vb = getter(b)
    if (typeof va === 'string' || typeof vb === 'string') {
      const cmp = String(va).localeCompare(String(vb), 'zh-CN')
      return sortDir.value === 'asc' ? cmp : -cmp
    }
    return sortDir.value === 'asc' ? va - vb : vb - va
  })
  return list
})

onMounted(() => {
  loadMetrics()
})
</script>

<template>
  <div class="sitebonus-page-wrapper">
    <VToolbar density="comfortable" class="sticky-toolbar">
      <div class="text-h6 ms-3">📊 站点魔力值监控</div>
      <VSpacer />
      <VChip v-if="lastUpdated" size="small" variant="tonal" color="primary">
        更新于 {{ lastUpdated }}
      </VChip>
      <VBtn
        variant="text"
        prepend-icon="mdi-bell-ring-outline"
        :loading="testSending"
        @click="sendTestNotification"
      >
        发送测试通知
      </VBtn>
      <VBtn icon="mdi-refresh" variant="text" :loading="loading" class="ms-2" @click="loadMetrics()" />
      <VBtn icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />
    <div class="sitebonus-app-page">
      <VAlert v-if="error" type="error" variant="tonal" closable class="mb-3" @click:close="error = ''">
        {{ error }}
      </VAlert>

      <VSnackbar
        v-model="testMessage"
        :timeout="3000"
        location="top"
        color="primary"
      >
        {{ testMessage }}
      </VSnackbar>

      <div class="summary-grid mb-2">
        <VCard variant="tonal" class="summary-card">
          <VCardText class="d-flex flex-column summary-text">
            <div class="text-caption text-medium-emphasis">启用站点</div>
            <div class="text-h5 text-primary mt-1">{{ summary.sites }}</div>
            <div class="mt-auto text-caption text-medium-emphasis summary-sub">&nbsp;</div>
          </VCardText>
        </VCard>
        <VCard variant="tonal" class="summary-card">
          <VCardText class="d-flex flex-column summary-text">
            <div class="text-caption text-medium-emphasis">总魔力值</div>
            <div class="text-h5 text-primary mt-1">{{ summary.bonus.toFixed(2) }}</div>
            <div class="mt-auto text-caption text-medium-emphasis summary-sub">来自 {{ summary.sites }} 个站点</div>
          </VCardText>
        </VCard>
        <VCard variant="tonal" class="summary-card">
          <VCardText class="d-flex flex-column summary-text">
            <div class="text-caption text-medium-emphasis">总做种数</div>
            <div class="text-h5 text-primary mt-1">{{ summary.seeding }}</div>
            <div class="mt-auto text-caption text-medium-emphasis summary-sub">活跃种子总数</div>
          </VCardText>
        </VCard>
        <VCard variant="tonal" class="summary-card">
          <VCardText class="d-flex flex-column summary-text">
            <div class="text-caption text-medium-emphasis">总时魔 (24h)</div>
            <div class="text-h5 text-primary mt-1">
              {{ summary.hourly >= 0 ? '+' : '' }}{{ summary.hourly.toFixed(4) }}
            </div>
            <div class="mt-auto text-caption text-medium-emphasis summary-sub">{{ summary.validCount }} / {{ summary.sites }} 个站点有效</div>
          </VCardText>
        </VCard>
      </div>

      <VAlert type="info" variant="tonal" density="compact" class="my-3">
        时魔 = 最近 24 小时内最早与最新魔力值快照的差值 / 小时数；点击表头切换排序。
      </VAlert>

      <VTable density="compact" hover>
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              :class="`text-${col.align} sortable-th`"
              @click="toggleSort(col.key)"
            >
              <span class="th-inner">
                <span>{{ col.label }}</span>
                <VIcon :icon="sortIcon(col.key)" size="small" class="ms-1 sort-icon" />
              </span>
            </th>
          </tr>
        </thead>
        <tbody v-if="sortedMetrics.length">
          <tr v-for="row in sortedMetrics" :key="row.site_id">
            <td class="ps-2">
              <a :href="row.url" target="_blank" rel="noopener" class="text-primary">{{ row.site_name }}</a>
            </td>
            <td>{{ row.username || '-' }}</td>
            <td>{{ row.user_level || '-' }}</td>
            <td class="text-end">{{ row.bonus.toFixed(2) }}</td>
            <td class="text-end">{{ row.seeding }}</td>
            <td class="text-end">
              <VChip size="x-small" :color="(row.hourly_bonus ?? 0) >= 0 ? 'primary' : 'grey'" variant="tonal">
                {{ formatHourlyBonus(row.hourly_bonus) }}
              </VChip>
            </td>
            <td class="text-end">{{ formatTb(row.upload_gb) }}</td>
            <td class="text-end">{{ formatTb(row.download_gb) }}</td>
            <td class="text-end">{{ row.ratio.toFixed(3) }}</td>
            <td class="text-end">{{ row.window_hours.toFixed(1) }}</td>
            <td class="text-caption">{{ row.updated_at || '-' }}</td>
          </tr>
        </tbody>
        <tbody v-else>
          <tr>
            <td colspan="11" class="text-center text-medium-emphasis py-4">
              {{ loading ? '加载中…' : '暂无站点数据' }}
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>
  </div>
</template>

<style scoped>
.sticky-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgb(var(--v-theme-surface));
}
.sitebonus-app-page {
  padding: 16px;
}
.sortable-th {
  cursor: pointer;
  user-select: none;
}
.sortable-th:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}
.th-inner {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.sort-icon {
  opacity: 0.55;
}
.sortable-th:hover .sort-icon {
  opacity: 1;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
@media (min-width: 960px) {
  .summary-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
.summary-card {
  height: 100%;
  min-height: 110px;
}
.summary-text {
  height: 100%;
}
.summary-sub {
  min-height: 1.2em;
  line-height: 1.2em;
}
</style>