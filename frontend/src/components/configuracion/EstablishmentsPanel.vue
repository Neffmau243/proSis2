<script setup lang="ts">
import { useEstablishmentsAdmin } from '@/composables/useEstablishmentsAdmin'
import EstablishmentFormDialog from './EstablishmentFormDialog.vue'
import AdminPageHeader from './AdminPageHeader.vue'
const {
  items,
  total,
  page,
  search,
  includeInactive,
  loading,
  error,
  load,
  applySearch,
  formVisible,
  editing,
  saving,
  formError,
  draft,
  open,
  save,
  toggle,
} = useEstablishmentsAdmin()
</script>
<template>
  <section class="establishments care-config">
    <AdminPageHeader
      title="Establecimientos"
      description="Comienza por una sede para organizar sus áreas, consultorios y servicios."
    >
      <el-button type="primary" @click="open()">Nuevo establecimiento</el-button>
    </AdminPageHeader>
    <el-form inline class="filters" @submit.prevent="applySearch"
      ><el-input
        v-model="search"
        clearable
        aria-label="Buscar establecimiento"
        placeholder="Nombre, RENAES o IDEESS"
        @clear="applySearch" /><el-button native-type="submit">Buscar</el-button
      ><el-switch
        v-model="includeInactive"
        active-text="Incluir inactivos"
        aria-label="Incluir establecimientos inactivos"
    /></el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false"
      ><el-button link @click="load">Reintentar</el-button></el-alert
    >
    <div v-loading="loading" :aria-busy="loading">
      <p v-if="!loading && !items.length" role="status">
        No hay establecimientos para estos filtros.
      </p>
      <article v-for="item in items" :key="item.id" class="establishment-row">
        <div>
          <h3>
            <router-link
              :to="{ name: 'establecimiento-detalle', params: { establishmentId: item.id } }"
              >{{ item.nombre }}</router-link
            >
          </h3>
          <p>
            {{ item.codigo_renaes ? `RENAES: ${item.codigo_renaes}` : 'Sin código RENAES' }} ·
            {{ item.consultorios_total }} consultorios
          </p>
          <p v-if="item.ubicacion">{{ item.ubicacion }}</p>
          <el-tag :type="item.activo ? 'success' : 'info'">{{
            item.activo ? 'Activo' : 'Inactivo'
          }}</el-tag>
        </div>
        <div class="row-actions">
          <router-link
            :to="{ name: 'establecimiento-detalle', params: { establishmentId: item.id } }"
            >Ver áreas y consultorios</router-link
          ><el-button :disabled="saving" @click="open(item)">Editar</el-button
          ><el-button :disabled="saving" @click="toggle(item)">{{
            item.activo ? 'Dar de baja' : 'Reactivar'
          }}</el-button>
        </div>
      </article>
    </div>
    <el-pagination
      v-if="total > 25"
      v-model:current-page="page"
      :total="total"
      :page-size="25"
      layout="prev, pager, next"
    />
    <EstablishmentFormDialog
      v-model="formVisible"
      :draft="draft"
      :editing="!!editing"
      :saving="saving"
      :error="formError"
      @change="Object.assign(draft, $event)"
      @save="save"
    />
  </section>
</template>
<style scoped>
.establishment-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  flex-wrap: wrap;
}
.establishment-row h3 {
  margin: 0;
}
.establishment-row p {
  color: var(--el-text-color-regular);
  line-height: 1.6;
  margin: 8px 0;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 24px;
}
.filters .el-input {
  width: 300px;
  max-width: 100%;
}
.establishment-row {
  padding-block: 24px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  overflow-wrap: anywhere;
}
.row-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.row-actions .el-button {
  margin: 0;
}
a {
  color: var(--care-link-color);
  text-underline-offset: 3px;
}
.establishment-row h3 {
  font-size: 18px;
}
@media (max-width: 600px) {
  .row-actions :is(a, button),
  .filters .el-button {
    min-height: 44px;
    align-content: center;
  }
}
</style>
