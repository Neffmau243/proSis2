<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import {
  establecimientosAdmin,
  areasAtencion,
  type EstablishmentAdmin,
  type CareArea,
} from '@/services/configuracionAtencion'
import { consultorios, type OfficeResponse } from '@/services/consultorios'
import AdminPageHeader from './AdminPageHeader.vue'
import type { CareNavigationContext } from '@/utils/careNavigation'
import { useEstablishmentsAdmin } from '@/composables/useEstablishmentsAdmin'
import EstablishmentFormDialog from './EstablishmentFormDialog.vue'
const props = defineProps<{ establishmentId: number }>()
const emit = defineEmits<{ context: [value: CareNavigationContext] }>()
const site = shallowRef<EstablishmentAdmin | null>(null),
  offices = shallowRef<OfficeResponse[]>([]),
  areas = shallowRef<CareArea[]>([])
const loading = shallowRef(false),
  error = shallowRef<string | null>(null),
  selectedArea = shallowRef<string | null>(null)
const activeAreas = computed(() => areas.value.filter((item) => item.activo))
const {
  open,
  toggle,
  saving,
  formVisible,
  editing,
  formError,
  draft,
  save,
  error: mutationError,
} = useEstablishmentsAdmin({ autoLoad: false, onChanged: load })
watch(
  () => ({ establishmentId: props.establishmentId, establishmentName: site.value?.nombre }),
  (value) => emit('context', value),
  { immediate: true },
)
const groups = computed(() => {
  const result = new Map<string, { code: string; name: string; items: OfficeResponse[] }>()
  for (const office of offices.value) {
    const code = office.area_codigo || office.especialidad_codigo || ''
    if (!result.has(code))
      result.set(code, {
        code,
        name:
          office.area_nombre ||
          areas.value.find((item) => item.codigo === code)?.nombre ||
          'Sin área',
        items: [],
      })
    result.get(code)!.items.push(office)
  }
  return [...result.values()].sort((a, b) => a.name.localeCompare(b.name, 'es'))
})
let request = 0
async function load() {
  const current = ++request
  loading.value = true
  error.value = null
  mutationError.value = null
  site.value = null
  try {
    const [entry, rooms, categories] = await Promise.all([
      establecimientosAdmin.get(props.establishmentId),
      consultorios.list({ establecimientoId: props.establishmentId, incluirInactivos: true }),
      areasAtencion.list(true),
    ])
    if (current === request) {
      site.value = entry
      offices.value = rooms
      areas.value = categories
    }
  } catch (cause) {
    if (current === request)
      error.value = cause instanceof Error ? cause.message : 'No se pudo cargar el establecimiento.'
  } finally {
    if (current === request) loading.value = false
  }
}
function context(areaCode?: string, create = false) {
  return {
    name: 'consultorios',
    query: {
      establecimientoId: String(props.establishmentId),
      ...(areaCode ? { areaCodigo: areaCode } : {}),
      ...(create ? { nuevo: '1' } : {}),
    },
  }
}
watch(
  () => props.establishmentId,
  () => {
    selectedArea.value = null
    void load()
  },
  { immediate: true },
)
</script>
<template>
  <el-alert
    v-if="error || mutationError"
    :title="error || mutationError || ''"
    type="error"
    :closable="false"
    ><el-button link @click="load">Reintentar</el-button></el-alert
  >
  <p v-if="loading" role="status">Cargando establecimiento…</p>
  <section v-if="site" class="establishment-detail care-config">
    <AdminPageHeader
      :title="site.nombre"
      :description="
        [site.codigo_renaes ? `RENAES: ${site.codigo_renaes}` : 'Sin código RENAES', site.ubicacion]
          .filter(Boolean)
          .join(' · ')
      "
    >
      <template #meta>
        <el-tag :type="site.activo ? 'success' : 'info'">{{
          site.activo ? 'Activo' : 'Inactivo'
        }}</el-tag>
      </template>
      <el-button :disabled="saving" @click="open(site)">Editar establecimiento</el-button>
      <el-button :disabled="saving" @click="toggle(site)">{{
        site.activo ? 'Dar de baja establecimiento' : 'Reactivar establecimiento'
      }}</el-button>
      <router-link :to="{ name: 'establecimientos' }">Volver a establecimientos</router-link>
    </AdminPageHeader>
    <h3>Áreas y consultorios</h3>
    <p class="site-help">
      Las áreas se comparten entre establecimientos. Aquí se muestran las que ya tienen consultorios
      en esta sede.
    </p>
    <div v-if="site.activo" class="create-office">
      <el-select
        v-model="selectedArea"
        clearable
        filterable
        placeholder="Área del nuevo consultorio"
        aria-label="Área del nuevo consultorio"
        ><el-option
          v-for="item in activeAreas"
          :key="item.codigo"
          :value="item.codigo"
          :label="item.nombre" /></el-select
      ><router-link v-if="selectedArea" :to="context(selectedArea, true)"
        >Crear consultorio en esta área</router-link
      ><router-link :to="{ name: 'areas-atencion' }">Gestionar catálogo de áreas</router-link>
    </div>
    <p v-if="!groups.length" role="status">
      Este establecimiento todavía no tiene consultorios. Selecciona un área para crear el primero.
    </p>
    <article v-for="group in groups" :key="group.code" class="site-area">
      <div class="group-heading">
        <h3>{{ group.name }}</h3>
        <router-link :to="context(group.code)">Ver consultorios del área</router-link>
      </div>
      <ul>
        <li v-for="office in group.items" :key="office.id">
          <router-link
            :to="{
              name: 'consultorio-servicios',
              params: { officeId: office.id },
              query: { establecimientoId: String(establishmentId), areaCodigo: group.code },
            }"
            >{{ office.nombre }}</router-link
          ><span> · {{ office.codigo }} · {{ office.activo ? 'Activo' : 'Inactivo' }}</span>
        </li>
      </ul>
    </article>
    <details class="fua-context">
      <summary>Consultar configuración actual de FUA</summary>
      <dl>
        <dt>Personal que atiende</dt>
        <dd>{{ site.fua_personal_atiende }}</dd>
        <dt>Lugar de atención</dt>
        <dd>{{ site.fua_lugar_atencion }}</dd>
        <dt>Código AISPED</dt>
        <dd>{{ site.fua_codigo_aisped || 'Sin configurar' }}</dd>
        <dt>RENIPRESS preimpreso</dt>
        <dd>{{ site.fua_renipress_preimpreso ? 'Sí' : 'No' }}</dd>
      </dl>
      <p class="site-help">
        Datos de consulta. La gestión de nombre y ubicación conserva esta configuración.
      </p>
    </details>
  </section>
  <EstablishmentFormDialog
    v-model="formVisible"
    :draft="draft"
    :editing="!!editing"
    :saving="saving"
    :error="formError"
    @change="Object.assign(draft, $event)"
    @save="save"
  />
</template>
<style scoped>
.group-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  align-items: flex-start;
}
.site-help {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  max-width: 70ch;
}
.create-office {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-block: 24px;
}
.create-office .el-select {
  width: 300px;
  max-width: 100%;
}
.site-area {
  padding-block: 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  overflow-wrap: anywhere;
}
.group-heading h3 {
  margin: 0;
}
li {
  margin-block: 16px;
  line-height: 1.6;
}
a {
  color: var(--care-link-color);
  text-underline-offset: 3px;
}
.fua-context {
  margin-top: 32px;
}
summary {
  cursor: pointer;
  padding-block: 12px;
}
dd {
  margin: 4px 0 16px;
}
dt {
  font-weight: 600;
}
@media (max-width: 600px) {
  .establishment-detail a {
    display: inline-block;
    min-height: 44px;
    align-content: center;
  }
  .create-office :deep(.el-select__wrapper) {
    min-height: 44px;
  }
}
</style>
