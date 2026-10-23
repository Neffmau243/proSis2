import { createRouter, createWebHistory } from 'vue-router'

import { isSessionExpired, loadSession } from '@/services/session-storage'

// Tipado adicional para el meta de cada ruta.
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    /** Permisos (códigos del backend) requeridos para ver la ruta. */
    permissions?: string[]
    /** Permisos alternativos: basta con tener uno de ellos. */
    permissionsAny?: string[]
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: 'Iniciar sesión' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'inicio',
          component: () => import('@/views/DashboardView.vue'),
          // Sin `permissions`: es la ruta de destino del guard cuando falta un
          // permiso. Todos los roles tienen PACIENTE_LEER, y declararlo aquí
          // provocaría un redirect infinito si algún día no lo tuvieran.
          meta: { title: 'Base de datos' },
        },
        {
          path: 'laboratorio',
          name: 'laboratorio',
          component: () => import('@/views/LaboratorioView.vue'),
          meta: { title: 'Laboratorio', permissions: ['PACIENTE_LEER'] },
        },
        {
          path: 'cuenta/cambiar-contrasena',
          name: 'cambiar-contrasena',
          component: () => import('@/views/CambiarContrasenaView.vue'),
          meta: { title: 'Cambiar contraseña' },
        },
        {
          // La tabla Base de datos del dashboard reemplaza el listado clásico.
          path: 'pacientes',
          redirect: { name: 'inicio' },
        },
        {
          path: 'admision',
          name: 'admision',
          component: () => import('@/views/AdmisionView.vue'),
          meta: { title: 'Admisión de paciente', permissions: ['ATENCION_CREAR'] },
        },
        {
          path: 'pacientes/nuevo',
          name: 'paciente-nuevo',
          component: () => import('@/views/PacienteNuevoView.vue'),
          meta: { title: 'Nuevo paciente', permissions: ['PACIENTE_EDITAR'] },
        },
        {
          path: 'pacientes/:id',
          name: 'paciente-detalle',
          component: () => import('@/views/PacienteDetalleView.vue'),
          meta: { title: 'Ficha del paciente', permissions: ['PACIENTE_LEER'] },
        },
        {
          path: 'pacientes/:id(\\d+)/editar',
          name: 'paciente-editar',
          component: () => import('@/views/PacienteEditarView.vue'),
          props: (route) => ({ patientId: Number(route.params.id) }),
          meta: { title: 'Editar paciente', permissions: ['PACIENTE_LEER', 'PACIENTE_EDITAR'] },
        },
        {
          path: 'atenciones',
          name: 'atenciones',
          // Pantalla general oculta: la consulta continúa en la ficha del paciente.
          redirect: { name: 'inicio' },
        },
        {
          path: 'atenciones/nueva',
          name: 'atencion-nueva',
          // Conserva enlaces antiguos sin abrir un segundo formulario de registro.
          redirect: (to) => {
            const rawId = to.query.patientId ?? to.query.pacienteId
            const id = typeof rawId === 'string' ? Number(rawId) : NaN
            return Number.isSafeInteger(id) && id > 0
              ? { name: 'admision', query: { patientId: String(id) } }
              : { name: 'inicio' }
          },
        },
        {
          path: 'atenciones/:id',
          name: 'atencion-detalle',
          component: () => import('@/views/AtencionDetalleView.vue'),
          meta: { title: 'Detalle de atención', permissions: ['ATENCION_LEER'] },
        },
        {
          // Profesionales y cuentas comparten una sola ruta con pestañas;
          // la vista decide qué mostrar según cada permiso.
          path: 'configuracion/personal',
          name: 'personal',
          component: () => import('@/views/PersonalView.vue'),
          meta: {
            title: 'Personal y cuentas',
            permissionsAny: ['PROFESIONAL_GESTIONAR', 'USUARIO_GESTIONAR'],
          },
        },
        {
          // Enlaces antiguos: cada uno abre su pestaña correspondiente.
          path: 'configuracion/usuarios',
          redirect: { name: 'personal', query: { tab: 'cuentas' } },
        },
        {
          path: 'configuracion/auditoria',
          name: 'auditoria',
          component: () => import('@/views/AuditoriaView.vue'),
          meta: { title: 'Auditoría', permissions: ['AUDITORIA_LEER'] },
        },
        {
          path: 'configuracion/grupos-etarios',
          name: 'grupos-etarios',
          component: () => import('@/views/GruposEtariosView.vue'),
          meta: {
            title: 'Grupos etarios',
            permissions: ['GRUPO_ETARIO_CONFIGURAR'],
          },
        },
        {
          path: 'configuracion/profesionales',
          redirect: { name: 'personal' },
        },
        {
          path: 'configuracion/establecimientos',
          name: 'establecimientos',
          component: () => import('@/views/EstablecimientosView.vue'),
          meta: { title: 'Establecimientos', permissions: ['CONSULTORIO_GESTIONAR'] },
        },
        {
          path: 'configuracion/establecimientos/:establishmentId(\\d+)',
          name: 'establecimiento-detalle',
          component: () => import('@/views/EstablecimientoDetalleView.vue'),
          props: (route) => ({ establishmentId: Number(route.params.establishmentId) }),
          meta: {
            title: 'Áreas y consultorios del establecimiento',
            permissions: ['CONSULTORIO_GESTIONAR'],
          },
        },
        {
          path: 'configuracion/areas',
          name: 'areas-atencion',
          component: () => import('@/views/AreasAtencionView.vue'),
          meta: { title: 'Áreas de atención', permissions: ['CONSULTORIO_GESTIONAR'] },
        },
        {
          path: 'configuracion/servicios',
          name: 'servicios-asistenciales',
          component: () => import('@/views/ServiciosView.vue'),
          meta: { title: 'Catálogo de servicios', permissions: ['CONSULTORIO_GESTIONAR'] },
        },
        {
          path: 'configuracion/consultorios',
          name: 'consultorios',
          component: () => import('@/views/ConsultoriosView.vue'),
          meta: { title: 'Consultorios', permissions: ['CONSULTORIO_GESTIONAR'] },
        },
        {
          path: 'configuracion/consultorios/:officeId(\\d+)',
          name: 'consultorio-servicios',
          component: () => import('@/views/ConsultoriosView.vue'),
          props: (route) => ({ officeId: Number(route.params.officeId) }),
          meta: { title: 'Servicios del consultorio', permissions: ['CONSULTORIO_GESTIONAR'] },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const session = loadSession()

  if (to.meta.requiresAuth) {
    if (!session || isSessionExpired(session)) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    // Los permisos viajan en el token/sesión; el backend sigue siendo la
    // autoridad final, esto solo oculta rutas en la interfaz.
    if (to.meta.permissions?.length) {
      const missing = to.meta.permissions.filter(
        (permission) => !session.permisos.includes(permission),
      )
      if (missing.length > 0) {
        return { name: 'inicio' }
      }
    }
    if (to.meta.permissionsAny?.length) {
      const allowed = to.meta.permissionsAny.some((permission) =>
        session.permisos.includes(permission),
      )
      if (!allowed) {
        return { name: 'inicio' }
      }
    }
  }

  if (to.name === 'login' && session && !isSessionExpired(session)) {
    return { name: 'inicio' }
  }

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} · Sistema de Salud IPRESS`
    : 'Sistema de Salud IPRESS'
})

export default router
