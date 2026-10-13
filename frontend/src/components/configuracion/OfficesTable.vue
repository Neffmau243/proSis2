<script setup lang="ts">
import { computed } from 'vue'
import type { OfficeResponse } from '@/services/consultorios'
import { officeTree } from '@/utils/officeHierarchy'

const props = defineProps<{
  rows: OfficeResponse[]
  loading: boolean
  establishmentNames: Record<number, string>
  specialtyNames: Record<string, string>
}>()
const emit = defineEmits<{
  edit: [row: OfficeResponse]
  assignments: [row: OfficeResponse]
  deactivate: [row: OfficeResponse]
}>()
function serviceNames(row: OfficeResponse): string {
  if (row.servicios_habilitados)
    return (
      row.servicios_habilitados.map((item) => item.nombre).join(', ') || 'Sin servicios habilitados'
    )
  return props.specialtyNames[row.especialidad_codigo || ''] || 'Sin servicios habilitados'
}
const tree = computed(() => officeTree(props.rows))
function parentName(row: OfficeResponse): string {
  if (row.consultorio_padre_id === null) return 'Principal'
  return (
    row.consultorio_padre_nombre ||
    props.rows.find((item) => item.id === row.consultorio_padre_id)?.nombre ||
    `Consultorio #${row.consultorio_padre_id}`
  )
}
</script>

<template>
  <el-table
    v-loading="loading"
    :data="tree"
    row-key="id"
    default-expand-all
    :tree-props="{ children: 'children' }"
    empty-text="Sin consultorios registrados"
    class="offices-table"
  >
    <el-table-column
      prop="nombre"
      label="Nombre / jerarquía"
      min-width="210"
      show-overflow-tooltip
    />
    <el-table-column prop="codigo" label="Código" width="100" show-overflow-tooltip />
    <el-table-column label="Establecimiento" min-width="180" show-overflow-tooltip>
      <template #default="{ row }">{{
        row.establecimiento_nombre ||
        establishmentNames[row.establecimiento_id] ||
        `Sede #${row.establecimiento_id}`
      }}</template>
    </el-table-column>
    <el-table-column label="Área" min-width="135" show-overflow-tooltip>
      <template #default="{ row }">{{
        row.area_nombre || specialtyNames[row.especialidad_codigo] || 'Sin área'
      }}</template>
    </el-table-column>
    <el-table-column label="Servicios / especialidades" min-width="260">
      <template #default="{ row }">
        {{ serviceNames(row) }}
      </template>
    </el-table-column>
    <el-table-column label="Consultorio padre" min-width="165" show-overflow-tooltip>
      <template #default="{ row }">{{ parentName(row) }}</template>
    </el-table-column>
    <el-table-column label="Estado" width="135">
      <template #default="{ row }">
        <el-tag
          :type="row.activo && row.activo_efectivo !== false ? 'success' : 'danger'"
          size="small"
        >
          {{
            !row.activo ? 'Inactivo' : row.activo_efectivo === false ? 'Padre inactivo' : 'Activo'
          }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="Acciones" min-width="240">
      <template #default="{ row }">
        <div class="actions-cell">
          <el-button link type="primary" @click="emit('edit', row)">Editar</el-button>
          <el-button link type="primary" @click="emit('assignments', row)">Asignaciones</el-button>
          <el-button link type="primary" :disabled="!row.activo" @click="emit('deactivate', row)"
            >Dar de baja</el-button
          >
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.offices-table :deep(.cell) {
  word-break: normal;
  overflow-wrap: anywhere;
}
.actions-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 10px;
}
.actions-cell :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
