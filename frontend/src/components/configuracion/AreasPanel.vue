<script setup lang="ts">
import AreaFormDialog from './AreaFormDialog.vue'
import AdminPageHeader from './AdminPageHeader.vue'
import { useCareAreas } from '@/composables/useCareAreas'
const {
  filtered,
  search,
  includeInactive,
  loading,
  saving,
  error,
  load,
  visible,
  editing,
  name,
  formError,
  open,
  save,
  toggle,
} = useCareAreas()
</script>
<template>
  <section class="care-areas care-config">
    <AdminPageHeader
      title="Áreas de atención"
      description="Categorías compartidas por los establecimientos. Cada consultorio selecciona un área y habilita sus servicios."
    >
      <el-button type="primary" @click="open()">Nueva área</el-button>
    </AdminPageHeader>
    <div class="area-filters">
      <el-input
        v-model="search"
        clearable
        aria-label="Buscar área"
        placeholder="Buscar área"
      /><el-switch
        v-model="includeInactive"
        active-text="Incluir inactivas"
        aria-label="Incluir áreas inactivas"
      />
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false"
      ><el-button link @click="load">Reintentar</el-button></el-alert
    >
    <div v-loading="loading" :aria-busy="loading">
      <p v-if="!loading && !filtered.length" role="status">No hay áreas para estos filtros.</p>
      <article v-for="item in filtered" :key="item.codigo" class="area-row">
        <div class="area-description">
          <h3>{{ item.nombre }}</h3>
          <el-tag :type="item.activo ? 'success' : 'info'">{{
            item.activo ? 'Activa' : 'Inactiva'
          }}</el-tag>
          <p v-if="item.es_area_base" class="area-help">
            Área base del sistema. Se conserva para los servicios existentes.
          </p>
          <details v-if="item.consultorios.length">
            <summary>Ver consultorios ({{ item.consultorios.length }})</summary>
            <ul>
              <li v-for="office in item.consultorios" :key="office.id">
                <router-link
                  :to="{ name: 'consultorio-servicios', params: { officeId: office.id } }"
                  >{{ office.nombre }}</router-link
                >
                · {{ office.establecimiento_nombre }}{{ office.activo ? '' : ' · Inactivo' }}
              </li>
            </ul>
          </details>
          <p v-else class="area-help">Todavía no tiene consultorios.</p>
        </div>
        <div class="area-actions">
          <router-link :to="{ name: 'consultorios', query: { areaCodigo: item.codigo } }"
            >Ver consultorios del área</router-link
          ><router-link
            :to="{ name: 'servicios-asistenciales', query: { areaCodigo: item.codigo } }"
            >Ver servicios</router-link
          ><el-button
            :disabled="saving"
            :aria-label="`Editar área ${item.nombre}`"
            @click="open(item)"
            >Editar</el-button
          ><el-button
            :disabled="saving || (item.es_area_base && item.activo)"
            @click="toggle(item)"
            >{{ item.activo ? 'Dar de baja' : 'Reactivar' }}</el-button
          >
        </div>
      </article>
    </div>
    <AreaFormDialog
      v-model="visible"
      v-model:name="name"
      :editing="!!editing"
      :saving="saving"
      :error="formError"
      @save="save"
    />
  </section>
</template>
<style scoped>
.area-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  flex-wrap: wrap;
}
.area-row h3 {
  margin: 0 0 12px;
}
.area-filters {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.area-filters .el-input {
  width: 300px;
  max-width: 100%;
}
.area-row {
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-block: 24px;
  overflow-wrap: anywhere;
}
.area-description {
  flex: 1;
  min-width: min(100%, 240px);
}
.area-help {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  font-size: 13px;
}
.area-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.area-actions .el-button {
  margin: 0;
}
a {
  color: var(--care-link-color);
  text-underline-offset: 3px;
}
summary {
  cursor: pointer;
  padding-block: 8px;
}
li {
  margin-block: 12px;
  line-height: 1.6;
}
@media (max-width: 600px) {
  .care-areas :deep(.el-button),
  .care-areas :deep(.el-input__wrapper),
  .area-actions a,
  summary {
    min-height: 44px;
    align-content: center;
  }
}
</style>
