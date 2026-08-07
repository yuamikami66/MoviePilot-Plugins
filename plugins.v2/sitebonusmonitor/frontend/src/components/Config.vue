<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['save', 'close'])

const localConfig = ref({
  enabled: false,
  cron: '0 8 * * *',
  notify_only_success: true,
})

function cloneConfig(config) {
  return JSON.parse(JSON.stringify(config || {}))
}

function saveConfig() {
  emit('save', cloneConfig(localConfig.value))
}

onMounted(() => {
  localConfig.value = {
    enabled: Boolean(props.initialConfig.enabled),
    cron: String(props.initialConfig.cron || '0 8 * * *'),
    notify_only_success: Boolean(props.initialConfig.notify_only_success),
  }
})
</script>

<template>
  <div class="sitebonus-config">
    <VCard variant="tonal">
      <VCardTitle class="text-h6">📊 站点魔力值监控</VCardTitle>
      <VCardText>
        <VRow>
          <VCol cols="12">
            <VSwitch
              v-model="localConfig.enabled"
              label="启用插件"
              color="primary"
              density="comfortable"
              hide-details
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="localConfig.cron"
              label="定时推送 Cron"
              placeholder="0 8 * * *"
              prepend-inner-icon="mdi-clock-outline"
              hint="5 段标准 cron；留空则不推送通知"
              persistent-hint
            />
          </VCol>
          <VCol cols="12">
            <VSwitch
              v-model="localConfig.notify_only_success"
              label="仅在数据有变化时推送"
              color="primary"
              density="comfortable"
              hide-details
            />
          </VCol>
        </VRow>

        <VAlert type="info" variant="tonal" density="compact" class="mt-3">
          数据来源：MoviePilot 站点用户数据表（SiteUserData）。<br>
          时魔 = 最近 24 小时内最早与最新魔力值快照差值 / 小时数。
        </VAlert>
      </VCardText>
      <VDivider />
      <VCardActions>
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn variant="tonal" color="primary" @click="saveConfig">保存</VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped>
.sitebonus-config {
  padding: 16px;
}
</style>