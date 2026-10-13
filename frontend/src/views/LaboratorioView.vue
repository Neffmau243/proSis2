<script setup lang="ts">
import LaboratoryWorkspace from '@/components/laboratory/LaboratoryWorkspace.vue'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <LaboratoryWorkspace :key="route.fullPath" />
</template>
