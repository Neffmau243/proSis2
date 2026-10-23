<template>
  <AdminPageLayout>
    <AdminPageHeader title="Personal y cuentas" />

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="form-alert"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane v-if="canProfessionals" label="Profesionales" name="profesionales">
        <ProfessionalsPanel
          :rows="professionals"
          :loading="loadingProfessionals"
          :incluir-inactivos="incluirInactivosProfesionales"
          :linked-professional-ids="linkedProfessionalIds"
          :can-create-account="canUsers"
          :catalog-revision="catalogRevision"
          @refresh="loadProfessionals"
          @update:incluir-inactivos="incluirInactivosProfesionales = $event"
          @create-account="createAccountFor"
        />
      </el-tab-pane>

      <el-tab-pane v-if="canUsers" label="Cuentas de usuario" name="cuentas">
        <UsersPanel
          :rows="users"
          :loading="loadingUsers"
          :incluir-inactivos="incluirInactivosUsuarios"
          :professionals="professionals"
          :prefill-professional-id="prefillProfessionalId"
          @refresh="loadUsers"
          @update:incluir-inactivos="incluirInactivosUsuarios = $event"
          @consume-prefill="prefillProfessionalId = null"
        />
      </el-tab-pane>
      <el-tab-pane v-if="canProfessionals" label="Profesiones" name="catalogos" lazy>
        <StaffCatalogsPanel kind="profesion" @created="catalogRevision++" />
      </el-tab-pane>
    </el-tabs>
  </AdminPageLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AdminPageLayout from '@/components/configuracion/AdminPageLayout.vue'
import AdminPageHeader from '@/components/configuracion/AdminPageHeader.vue'

import ProfessionalsPanel from '@/components/configuracion/ProfessionalsPanel.vue'
import UsersPanel from '@/components/configuracion/UsersPanel.vue'
import StaffCatalogsPanel from '@/components/configuracion/StaffCatalogsPanel.vue'
import { profesionales, type ProfessionalResponse } from '@/services/profesionales'
import { usuarios, type UserResponse } from '@/services/usuarios'
import { useAuthStore } from '@/stores/auth'

type TabName = 'profesionales' | 'cuentas' | 'catalogos'

const route = useRoute()
const auth = useAuthStore()

const canProfessionals = computed(() => auth.hasPermission('PROFESIONAL_GESTIONAR'))
const canUsers = computed(() => auth.hasPermission('USUARIO_GESTIONAR'))

const professionals = ref<ProfessionalResponse[]>([])
const users = ref<UserResponse[]>([])
const loadingProfessionals = ref(false)
const loadingUsers = ref(false)
const errorMessage = ref<string | null>(null)

const incluirInactivosProfesionales = ref(false)
const incluirInactivosUsuarios = ref(false)
const prefillProfessionalId = ref<number | null>(null)
const catalogRevision = ref(0)

function initialTab(): TabName {
  if (route.query.tab === 'catalogos' && canProfessionals.value) return 'catalogos'
  if (route.query.tab === 'cuentas' && canUsers.value) return 'cuentas'
  if (canProfessionals.value) return 'profesionales'
  return 'cuentas'
}

const activeTab = ref<TabName>(initialTab())

/** Un solo GET alimenta el mapa de cuentas para el cruce con profesionales. */
const linkedProfessionalIds = computed(() =>
  users.value.map((user) => user.profesional_id).filter((id): id is number => id !== null),
)

async function loadProfessionals(): Promise<void> {
  if (!canProfessionals.value) return
  loadingProfessionals.value = true
  errorMessage.value = null
  try {
    professionals.value = await profesionales.list(incluirInactivosProfesionales.value)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo cargar la lista de profesionales.'
  } finally {
    loadingProfessionals.value = false
  }
}

async function loadUsers(): Promise<void> {
  if (!canUsers.value) return
  loadingUsers.value = true
  errorMessage.value = null
  try {
    users.value = await usuarios.list(incluirInactivosUsuarios.value)
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'No se pudo cargar la lista de usuarios.'
  } finally {
    loadingUsers.value = false
  }
}

function createAccountFor(professional: ProfessionalResponse): void {
  if (!canUsers.value) return
  prefillProfessionalId.value = professional.id
  activeTab.value = 'cuentas'
}

watch(incluirInactivosProfesionales, loadProfessionals)
watch(incluirInactivosUsuarios, loadUsers)

onMounted(() => {
  loadProfessionals()
  loadUsers()
})
</script>

<style scoped>
.form-alert {
  margin-bottom: 16px;
}
</style>
