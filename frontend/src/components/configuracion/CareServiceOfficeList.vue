<script setup lang="ts">
import type { CareServiceOffice } from '@/services/serviciosAsistenciales'

defineProps<{ offices: CareServiceOffice[] }>()
</script>

<template>
  <ul class="service-offices">
    <li v-for="office in offices" :key="office.id" class="service-office">
      <router-link
        class="service-office-name"
        :to="{ name: 'consultorio-servicios', params: { officeId: office.id } }"
        >{{ office.nombre }}</router-link
      >
      <span v-if="!office.activo" class="service-office-status"> · Inactivo</span>
      <p class="service-office-context">
        {{ office.establecimiento_nombre || `Establecimiento #${office.establecimiento_id}` }}
      </p>
    </li>
  </ul>
</template>

<style scoped>
.service-offices {
  list-style: none;
  padding: 0;
  margin: 12px 0;
}
.service-office {
  padding-block: 8px;
  overflow-wrap: anywhere;
}
.service-office-name {
  color: color-mix(in srgb, var(--el-color-primary) 65%, var(--el-text-color-primary));
  font-weight: 500;
  text-underline-offset: 3px;
}
.service-office-name:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 3px;
}
.service-office-context,
.service-office-status {
  margin: 4px 0 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}
@media (max-width: 900px) {
  .service-office-name {
    display: inline-block;
    min-height: 44px;
    align-content: center;
  }
}
</style>
