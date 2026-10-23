<script setup lang="ts">
defineProps<{ title: string; description?: string; titleId?: string }>()
</script>

<template>
  <header class="admin-page-header">
    <div class="admin-page-header__text">
      <h2 :id="titleId">{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
      <div v-if="$slots.meta" class="admin-page-header__meta"><slot name="meta" /></div>
    </div>
    <div v-if="$slots.default" class="admin-page-header__actions"><slot /></div>
  </header>
</template>

<style scoped>
.admin-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px 24px;
  margin-bottom: 24px;
}
.admin-page-header__text {
  min-width: 0;
  flex: 1 1 320px;
}
h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.35;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;
}
p {
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  max-width: 70ch;
}
.admin-page-header__meta {
  margin-top: 12px;
}
.admin-page-header__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.admin-page-header__actions :deep(.el-button) {
  margin-left: 0;
}
@media (max-width: 600px) {
  .admin-page-header__text {
    flex-basis: 100%;
  }
}
</style>
