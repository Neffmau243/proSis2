<script setup lang="ts">
import { shallowRef } from 'vue'
import AdminPageLayout from '@/components/configuracion/AdminPageLayout.vue'
import type { CareNavigationContext } from '@/utils/careNavigation'
import ConsultoriosPanel from '@/components/configuracion/ConsultoriosPanel.vue'
defineProps<{ officeId?: number }>()
const context = shallowRef<CareNavigationContext>({})
</script>

<template>
  <AdminPageLayout :context="context">
    <ConsultoriosPanel :office-id="officeId" @context="context = $event" />
  </AdminPageLayout>
</template>
