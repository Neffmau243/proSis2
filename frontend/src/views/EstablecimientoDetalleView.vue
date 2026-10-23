<script setup lang="ts">
import { shallowRef } from 'vue'
import AdminPageLayout from '@/components/configuracion/AdminPageLayout.vue'
import type { CareNavigationContext } from '@/utils/careNavigation'
import EstablishmentDetailPanel from '@/components/configuracion/EstablishmentDetailPanel.vue'
defineProps<{ establishmentId: number }>()
const context = shallowRef<CareNavigationContext>({})
</script>
<template>
  <AdminPageLayout :context="context">
    <EstablishmentDetailPanel :establishment-id="establishmentId" @context="context = $event" />
  </AdminPageLayout>
</template>
