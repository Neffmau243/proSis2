<script setup lang="ts">
import './careConfiguration.css'
import CareConfigurationNav from './CareConfigurationNav.vue'
import type { CareNavigationContext } from '@/utils/careNavigation'
defineProps<{ context?: CareNavigationContext }>()
</script>

<template>
  <div class="admin-page care-config">
    <CareConfigurationNav :context="context" />
    <div class="admin-workspace"><slot /></div>
  </div>
</template>

<style scoped>
.admin-page {
  width: 100%;
  min-width: 0;
}
.admin-workspace {
  padding: 24px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  min-width: 0;
}
@media (max-width: 600px) {
  .admin-workspace {
    padding: 20px 16px;
  }
}
</style>
