<script setup lang="ts">
import { computed, shallowRef, watch, type Component } from 'vue'
import { DocumentRemove, FirstAidKit, Tickets, User, Wallet } from '@element-plus/icons-vue'
import sisLogo from '@/assets/insurance/sis.png'
import essaludLogo from '@/assets/insurance/essalud.png'
import { isSisInsurance } from '@/utils/patientInsurance'
import type { IdCatalogItem } from '@/services/catalogos'

const props = defineProps<{
  insurance?: IdCatalogItem
  insuranceId?: number | null
}>()

const categories: Record<string, { label: string; icon: Component }> = {
  NINGUNO: { label: 'Sin seguro', icon: User },
  SIN_SEGURO: { label: 'Sin seguro', icon: User },
  SANIDAD: { label: 'Sanidad', icon: FirstAidKit },
  PARTICULAR: { label: 'Particular', icon: Wallet },
  OTRO: { label: 'Otro seguro', icon: Tickets },
}

// Los IDs son claves de base de datos; la identidad procede del catálogo.
const brand = computed(() => {
  const insurance = props.insurance
  if (!insurance) {
    return {
      label: props.insuranceId != null ? 'Seguro' : 'Sin registro',
      title:
        props.insuranceId != null
          ? 'Seguro pendiente de cargar del catálogo'
          : 'Seguro sin registrar',
      logo: null,
      shortLabel: props.insuranceId != null ? 'Seguro' : 'Sin registro',
      icon: props.insuranceId != null ? Tickets : DocumentRemove,
    }
  }
  const family = insurance.regimen || insurance.codigo
  if (isSisInsurance(insurance) || insurance.codigo.startsWith('SIS_')) {
    return {
      label: 'SIS · Seguro Integral de Salud',
      shortLabel: 'SIS',
      title: insurance.nombre,
      logo: sisLogo,
      icon: FirstAidKit,
    }
  }
  if (family === 'ESSALUD') {
    return {
      label: 'EsSalud · Seguro Social de Salud',
      shortLabel: 'EsSalud',
      title: insurance.nombre,
      logo: essaludLogo,
      icon: FirstAidKit,
    }
  }
  const category = categories[family]
  const label = category?.label || insurance.nombre
  return {
    label,
    shortLabel: label,
    title: insurance.nombre,
    logo: null,
    icon: category?.icon || Tickets,
  }
})
const failedLogo = shallowRef(false)
watch(
  () => brand.value.logo,
  () => {
    failedLogo.value = false
  },
)
</script>

<template>
  <span class="patient-insurance-brand" :title="brand.title">
    <img
      v-if="brand.logo && !failedLogo"
      class="patient-insurance-brand__logo"
      :src="brand.logo"
      :alt="brand.label"
      width="74"
      height="34"
      @error="failedLogo = true"
    />
    <span v-else class="patient-insurance-brand__fallback" :aria-label="brand.label">
      <component :is="brand.icon" class="patient-insurance-brand__icon" aria-hidden="true" />
      <span class="patient-insurance-brand__label">{{ brand.shortLabel }}</span>
    </span>
  </span>
</template>

<style scoped>
.patient-insurance-brand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  flex-shrink: 0;
  width: 90px;
  max-width: 100%;
  height: 52px;
  padding: 6px 7px;
  border: 1px solid var(--admission-border, #b9cbdf);
  border-radius: 4px;
  background: #fff;
  color: #304f6d;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.3;
  text-align: center;
}
.patient-insurance-brand__logo {
  display: block;
  width: 100%;
  height: 34px;
  object-fit: contain;
}
.patient-insurance-brand__fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 100%;
  min-width: 0;
}
.patient-insurance-brand__icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
}
.patient-insurance-brand__label {
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
