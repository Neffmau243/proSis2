<script setup lang="ts">
import { useRoute } from 'vue-router'
import AdminPageLayout from '@/components/configuracion/AdminPageLayout.vue'
import CareServiceCatalogPanel from '@/components/configuracion/CareServiceCatalogPanel.vue'
const route = useRoute()
</script>

<template>
  <AdminPageLayout>
    <CareServiceCatalogPanel
      :area-code="typeof route.query.areaCodigo === 'string' ? route.query.areaCodigo : undefined"
    />
  </AdminPageLayout>
</template>
