<template>
  <el-container class="app-layout" @keydown.esc="mobileMenuOpen = false">
    <el-button class="mobile-menu-toggle" :aria-expanded="mobileMenuOpen" aria-controls="app-navigation" @click="mobileMenuOpen = !mobileMenuOpen">
      {{ mobileMenuOpen ? 'Cerrar menú' : 'Abrir menú' }}
    </el-button>
    <el-aside id="app-navigation" width="264px" class="side" :class="{ 'side--mobile-open': mobileMenuOpen }">
      <!-- Marca -->
      <div class="side__brand">
        <span class="side__logo"><el-icon><FirstAidKit /></el-icon></span>
        <span class="side__brand-text">
          <span class="side__brand-name">IPRESS</span>
          <span class="side__brand-sub">Sistema de Salud</span>
        </span>
      </div>

      <!-- Paciente activo: contexto y acciones sobre la fila seleccionada -->
      <div v-if="can('PACIENTE_LEER')" class="side__patient" :class="{ 'is-empty': !seleccionado }">
        <template v-if="seleccionado">
          <span class="side__patient-label">Paciente seleccionado</span>
          <span class="side__patient-name">{{ nombreSeleccionado }}</span>
          <span class="side__patient-meta">
            {{ seleccionado.tipo_documento_codigo }} {{ seleccionado.numero_documento }}
            <template v-if="seleccionado.historia_clinica">
              · HC {{ seleccionado.historia_clinica }}
            </template>
          </span>
        </template>
        <span v-else class="side__patient-hint">
          Seleccione un paciente en la tabla Base de datos.
        </span>

        <div class="side__patient-actions">
          <el-button class="side__patient-action" :disabled="!seleccionado" @click="verPaciente">
            <el-icon><View /></el-icon>
            <span>Ver paciente</span>
          </el-button>
          <!-- OCULTO temporalmente para revisión visual: descomentar para restaurar.
          <el-button
            v-if="puedeModificarDatos"
            class="side__patient-action"
            :disabled="!seleccionado"
            @click="modificarDatos"
          >
            <el-icon><EditPen /></el-icon>
            <span>Modificar datos</span>
          </el-button>
          -->
          <el-button
            v-if="can('PACIENTE_DAR_BAJA')"
            class="side__patient-action side__patient-action--danger"
            :disabled="!puedeDarBaja"
            @click="borrarPaciente"
          >
            <el-icon><Delete /></el-icon>
            <span>Borrar paciente</span>
          </el-button>
        </div>
      </div>

      <!-- Acciones principales -->
      <div class="side__actions">
        <p class="side__section side__section--tight">Acciones</p>
        <el-button
          v-if="can('ATENCION_CREAR')"
          class="side__action side__action--primary"
          type="primary"
          :disabled="!seleccionado"
          @click="iniciarAdmision"
        >
          <el-icon><FirstAidKit /></el-icon>
          <span>Admisión</span>
        </el-button>
        <el-button
          v-if="can('PACIENTE_EDITAR')"
          class="side__action side__action--ghost"
          @click="nuevoPaciente"
        >
          <el-icon><Plus /></el-icon>
          <span>Paciente nuevo</span>
        </el-button>
        <el-button class="side__action side__action--ghost" @click="irLaboratorio">
          <el-icon><Files /></el-icon>
          <span>Ref. Laboratorio</span>
        </el-button>
      </div>

      <!-- Navegación -->
      <nav class="side__nav">
        <template v-for="section in navSections" :key="section.title">
          <p class="side__section">{{ section.title }}</p>
          <router-link
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            class="side__link"
            :class="{ 'is-active': isActive(item) }"
          >
            <el-icon class="side__link-icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <!-- Identidad del usuario y acciones de sesión -->
      <div class="side__footer">
        <div class="side__user">
          <span class="side__avatar">{{ iniciales }}</span>
          <span class="side__user-info">
            <span class="side__user-name" :title="nombreUsuario">{{ nombreUsuario }}</span>
            <span class="side__user-role">{{ auth.roles.join(' · ') || 'sin rol' }}</span>
          </span>
        </div>
        <div class="side__session">
          <el-button class="side__session-btn" title="Cambiar contraseña" @click="cambiarContrasena">
            <el-icon><Lock /></el-icon>
            <span>Contraseña</span>
          </el-button>
          <el-button class="side__session-btn side__salir" @click="salir">
            <el-icon><SwitchButton /></el-icon>
            <span>Salir</span>
          </el-button>
        </div>
      </div>
    </el-aside>

    <el-container class="app-layout__content">
      <!-- La identidad del usuario vive solo en el pie de la barra lateral. -->
      <el-header class="topbar" height="auto">
        <div class="topbar__title">{{ currentTitle }}</div>
        <div ref="topbarActions" class="topbar__actions" />
      </el-header>

      <el-main class="app-layout__main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, provide, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { usePacienteSeleccionado } from '@/composables/usePacienteSeleccionado'
import { pacientes } from '@/services/pacientes'
import { useAuthStore } from '@/stores/auth'
import { topbarActionsKey } from '@/layouts/topbar'

const topbarActions = useTemplateRef<HTMLElement>('topbarActions')
provide(topbarActionsKey, topbarActions)

interface NavItem {
  to: string
  label: string
  icon: string
  /** Rutas hijas que también deben marcar el ítem como activo. */
  match?: (path: string) => boolean
}

const route = useRoute()
const mobileMenuOpen = ref(false)
watch(() => route.fullPath, () => { mobileMenuOpen.value = false })
const router = useRouter()
const auth = useAuthStore()
const { seleccionado, seleccionar, notificarCambio } = usePacienteSeleccionado()

const currentTitle = computed(() => route.meta.title ?? '')

const nombreUsuario = computed(() => auth.nombreUsuario || 'Usuario')

const iniciales = computed(() => {
  const name = (auth.nombreUsuario || 'U').trim()
  return name
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
})

const nombreSeleccionado = computed(() => {
  const patient = seleccionado.value
  if (!patient) return ''
  return (
    [patient.apellido_paterno, patient.apellido_materno, patient.primer_nombre]
      .filter(Boolean)
      .join(' ') || patient.numero_documento
  )
})

/** Secciones de navegación filtradas por permiso (no por rol escrito). */
const navSections = computed(() => {
  const sections: { title: string; items: NavItem[] }[] = []

  const main: NavItem[] = []
  if (can('PACIENTE_LEER')) {
    main.push({
      to: '/',
      label: 'Base de datos',
      icon: 'Grid',
      match: (path) => path === '/' || path.startsWith('/pacientes'),
    })
  }
  // Ref. Laboratorio pasó al bloque de acciones principales, sobre la navegación.
  if (main.length) sections.push({ title: 'Principal', items: main })

  // El registro parte del paciente seleccionado y del botón Admisión.
  // El historial y el detalle se consultan dentro de la ficha del paciente.

  const admin: NavItem[] = []
  // Profesionales y cuentas viven en una sola vista con pestañas.
  if (canAny(['PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'])) {
    admin.push({ to: '/configuracion/personal', label: 'Personal y cuentas', icon: 'UserFilled' })
  }
  if (can('AUDITORIA_LEER')) admin.push({ to: '/configuracion/auditoria', label: 'Auditoría', icon: 'DataLine' })
  if (admin.length) sections.push({ title: 'Administración', items: admin })

  const config: NavItem[] = []
  if (can('GRUPO_ETARIO_CONFIGURAR')) {
    config.push({ to: '/configuracion/grupos-etarios', label: 'Grupos etarios', icon: 'Odometer' })
  }
  if (can('CONSULTORIO_GESTIONAR')) {
    config.push({ to: '/configuracion/consultorios', label: 'Consultorios', icon: 'OfficeBuilding' })
  }
  if (config.length) sections.push({ title: 'Configuración', items: config })

  return sections
})

function can(permission: string): boolean {
  return auth.hasPermission(permission)
}

/** Algunas entradas agrupan dos permisos: basta con tener uno. */
function canAny(permissions: string[]): boolean {
  return permissions.some((permission) => can(permission))
}

function isActive(item: NavItem): boolean {
  return item.match ? item.match(route.path) : route.path === item.to
}

/** Solo se ofrece la baja de un paciente activo y con el permiso explícito. */
const puedeDarBaja = computed(() => Boolean(seleccionado.value?.estado) && can('PACIENTE_DAR_BAJA'))

// OCULTO temporalmente junto con el botón "Modificar datos" (revisión visual).
// /**
//  * La corrección de datos del paciente vive en el contexto de admisión, por lo
//  * que además de editar el paciente hace falta el permiso clínico de esa ruta
//  * (ver el redirect de `pacientes/:id/editar` en el router).
//  */
// const puedeModificarDatos = computed(() => can('PACIENTE_EDITAR') && can('ATENCION_CREAR'))

function nuevoPaciente(): void {
  router.push({ name: 'paciente-nuevo' })
}

function irLaboratorio(): void {
  router.push({ name: 'laboratorio', query: seleccionado.value ? { paciente_id: seleccionado.value.id } : {} })
}

function verPaciente(): void {
  const patient = seleccionado.value
  if (!patient) return
  router.push({ name: 'paciente-detalle', params: { id: patient.id } })
}

// OCULTO temporalmente junto con el botón "Modificar datos" (revisión visual).
// function modificarDatos(): void {
//   const patient = seleccionado.value
//   if (!patient) return
//   // La corrección de datos del paciente vive en el contexto de admisión (ver router).
//   router.push({ name: 'admision', query: { patientId: String(patient.id) } })
// }

async function borrarPaciente(): Promise<void> {
  const patient = seleccionado.value
  if (!patient) return
  try {
    await ElMessageBox.confirm(
      `¿Dar de baja a ${nombreSeleccionado.value}? La baja es lógica: el historial se conserva.`,
      'Borrar paciente',
      { type: 'warning', confirmButtonText: 'Dar de baja', cancelButtonText: 'Cancelar' },
    )
  } catch {
    return
  }
  try {
    const result = await pacientes.deactivate(patient.id)
    ElMessage.success(result.mensaje)
    seleccionar(null)
    // La tabla Base de datos vuelve a consultar al ver cambiar la versión.
    notificarCambio()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : 'No se pudo dar de baja.')
  }
}

function iniciarAdmision(): void {
  const patient = seleccionado.value
  if (!patient) {
    ElMessage.warning('Seleccione un paciente en la tabla Base de datos.')
    return
  }
  router.push({ name: 'admision', query: { patientId: String(patient.id) } })
}

function salir(): void {
  auth.logout()
  router.push({ name: 'login' })
}

function cambiarContrasena(): void {
  router.push({ name: 'cambiar-contrasena' })
}
</script>

<style scoped>
.app-layout {
  height: 100%;
}

.app-layout__content { min-width: 0; min-height: 0; }
.mobile-menu-toggle { display: none; }

@media (max-width: 680px) {
  .app-layout { flex-direction: column; }
  .mobile-menu-toggle { display: flex; flex-shrink: 0; min-height: 44px; margin: 0; }
  .app-layout .side { display: none; width: 100%; max-height: 45vh; flex-shrink: 0; overflow-y: auto; }
  .app-layout .side--mobile-open { display: flex; }
  .app-layout .side > * { flex-shrink: 0; }
  .app-layout .side__nav { flex: none; overflow: visible; }
}

/* ---------- Barra lateral ---------- */
.side {
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-right: 1px solid var(--el-border-color-lighter);
}

.side__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 18px 14px;
}

.side__logo {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  font-size: 20px;
  color: #fff;
  background: linear-gradient(140deg, var(--el-color-primary), var(--el-color-primary-dark-2));
  box-shadow: 0 6px 14px -6px var(--el-color-primary);
}

.side__brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.side__brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--el-text-color-primary);
}

.side__brand-sub {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.side__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 16px 16px;
}

.side__action {
  width: 100%;
  height: 42px;
  margin-left: 0 !important;
  border-radius: 10px;
  font-weight: 600;
  justify-content: center;
}

.side__action--ghost {
  background-color: var(--el-fill-color-light);
  border-color: transparent;
  color: var(--el-text-color-primary);
}

.side__action--ghost:hover {
  background-color: var(--el-fill-color);
  border-color: transparent;
  color: var(--el-color-primary);
}

/* Acción principal: más alta y con sombra propia para jerarquizarla. */
.side__action--primary {
  height: 46px;
  font-size: 14px;
  box-shadow: 0 8px 16px -10px var(--el-color-primary);
}

.side__action--primary.is-disabled {
  box-shadow: none;
}

/* Tarjeta de paciente activo */
.side__patient {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0 16px 8px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--el-color-primary-light-7);
  background-color: var(--el-color-primary-light-9);
}

.side__patient.is-empty {
  border-style: dashed;
  border-color: var(--el-border-color);
  background-color: transparent;
}

.side__patient-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--el-color-primary);
}

.side__patient-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.side__patient-meta {
  font-size: 11.5px;
  color: var(--el-text-color-secondary);
}

.side__patient-hint {
  font-size: 11.5px;
  font-style: italic;
  color: var(--el-text-color-secondary);
}

.side__patient-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

/* Acciones sobre la fila seleccionada: filas compactas y alineadas a la izquierda. */
.side__patient-action {
  justify-content: flex-start;
  width: 100%;
  height: 32px;
  margin-left: 0 !important;
  padding: 0 6px;
  border-color: transparent;
  background-color: transparent;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 500;
}

.side__patient-action:hover:not(.is-disabled) {
  background-color: var(--el-color-primary-light-8);
  border-color: transparent;
  color: var(--el-color-primary);
}

.side__patient-action--danger {
  color: var(--el-color-danger);
}

.side__patient-action--danger:hover:not(.is-disabled) {
  background-color: var(--el-color-danger-light-9);
  border-color: transparent;
  color: var(--el-color-danger);
}

.side__patient-action.is-disabled {
  background-color: transparent;
  color: var(--el-text-color-disabled);
}

/* Navegación */
.side__nav {
  flex: 1;
  /* Sin min-height el bloque de navegación no puede encogerse y desborda
     cuando el contexto del paciente ocupa más alto. */
  min-height: 0;
  overflow-y: auto;
  padding: 4px 12px 12px;
}

.side__section {
  margin: 14px 8px 6px;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
}

.side__section:first-child {
  margin-top: 6px;
}

/* Título de sección dentro de un bloque con padding propio. */
.side__section.side__section--tight {
  margin: 0 0 2px;
}

.side__link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 9px;
  font-size: 13.5px;
  color: var(--el-text-color-primary);
  text-decoration: none;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.side__link:hover {
  background-color: var(--el-fill-color-light);
}

.side__link-icon {
  font-size: 17px;
  color: var(--el-text-color-secondary);
}

.side__link.is-active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}

.side__link.is-active .side__link-icon {
  color: var(--el-color-primary);
}

.side__link.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background-color: var(--el-color-primary);
}

/* Pie */
.side__footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.side__user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.side__avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-8);
}

.side__user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  overflow: hidden;
}

.side__user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.side__user-role {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

/* Acciones de sesión: dos botones en una fila para no ganar altura. */
.side__session {
  display: flex;
  gap: 8px;
}

.side__session-btn {
  flex: 1;
  height: 34px;
  margin-left: 0 !important;
  padding: 0 8px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  border-color: var(--el-border-color);
}

.side__session-btn:hover {
  background-color: var(--el-fill-color-light);
  border-color: transparent;
  color: var(--el-color-primary);
}

.side__salir {
  color: var(--el-color-danger);
  border-color: var(--el-color-danger-light-5);
}

.side__salir:hover {
  background-color: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-3);
  color: var(--el-color-danger);
}

/* ---------- Barra superior ---------- */
.topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  min-height: 52px;
  padding-block: 8px;
  background-color: #fff;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.topbar__title {
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 600;
}

.topbar__actions {
  min-width: 0;
  max-width: 100%;
  margin-left: auto;
}

.topbar__actions:empty {
  display: none;
}

@media (max-width: 680px) {
  .topbar__actions:not(:empty) {
    flex-basis: 100%;
    margin-left: 0;
  }
}

.app-layout__main {
  background-color: #f5f7fa;
  padding: 12px 14px;
}
</style>
