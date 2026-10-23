# Reorden de la administración de atención

Fecha: 22/10/2026. Implementación del recorrido principal propuesto en `PLAN_REORDEN_ADMINISTRACION_20261022.md`.

## Resultado

La navegación administrativa queda en el orden Establecimientos → Áreas de atención → Consultorios → Servicios / especialidades. Pacientes mantiene su registro y listado por separado. Personal y cuentas conserva el registro general de profesionales.

| Ruta | Función |
| --- | --- |
| `/configuracion/establecimientos` | Buscar, paginar, registrar, editar, dar de baja y reactivar establecimientos |
| `/configuracion/establecimientos/:id` | Consultar la sede y sus consultorios agrupados por área; continuar al alta con sede/área precargadas |
| `/configuracion/areas` | Mantener el catálogo compartido de áreas, consultar sus usos, editar nombres y gestionar el estado de áreas propias cuando sus dependencias lo permiten |
| `/configuracion/consultorios` | Directorio con filtros de establecimiento y área; alta/edición del consultorio |
| `/configuracion/consultorios/:id` | Servicios habilitados y profesionales asignados; conserva su enlace existente |
| `/configuracion/servicios` | Único mantenimiento general de servicios, con entrada filtrada por área |
| `/pacientes/:id/editar` | Editor de datos del paciente, independiente de Admisión |

Se retiraron las pestañas duplicadas de áreas y catálogo de servicios de Consultorios. Sus enlaces llevan a sus vistas propias. La navegación hacia el detalle de consultorio y de regreso conserva los filtros; el contexto de creación se consume sin guardar registros automáticamente.

## Alcance de datos y permisos

- La administración de establecimientos y áreas reutiliza `CONSULTORIO_GESTIONAR`. Se verifica en la API, rutas y menú. No se agregaron roles ni permisos clínicos.
- La edición de pacientes requiere `PACIENTE_LEER` y `PACIENTE_EDITAR`. Se habilita desde la ficha y el paciente seleccionado en el menú, sin conceder `ATENCION_CREAR` a ADMIN.
- El editor de paciente reutiliza `AdmissionPatientSummary` y sus validaciones existentes. No se modificó ese componente en esta entrega. Se protege la salida con cambios pendientes o un guardado en curso y se actualiza el listado al guardar.
- Establecimientos tiene contratos administrativos separados de los catálogos de lectura que utiliza la atención clínica. Las escrituras aceptan únicamente nombre, abreviatura, RENAES, IDEESS y distrito. Los demás datos persistidos se conservan.
- Las áreas siguen siendo un catálogo compartido; no se crea una copia por establecimiento. La presencia de un área en una sede se obtiene de sus consultorios actuales.
- Las áreas base permanecen protegidas contra bajas. Las áreas nuevas pueden darse de baja cuando no organizan consultorios, servicios o profesionales activos. Los códigos no cambian al renombrar.
- La baja de un establecimiento exige resolver primero sus consultorios activos. No ejecuta bajas en cascada. Reactivar una sede conserva el estado de sus consultorios.
- Los cambios se auditan y las transacciones revierten ante errores de persistencia o auditoría.

## Conservación de Admisión y FUA

Esta entrega no cambia el formulario clínico, la selección de servicio/profesional, los cálculos, las reglas de admisión ni la generación de FUA. No se modificaron sus contratos de lectura existentes.

Los valores específicos de FUA del establecimiento se muestran solo para consulta. La API administrativa rechaza cambios a esos valores; editar nombre o ubicación no los restablece. Un cambio explícito del identificador RENAES/RENIPRESS es un cambio administrativo del establecimiento: no reescribe los documentos históricos guardados.

No se ejecutaron migraciones ni se reestructuraron tablas, códigos o relaciones históricas en esta entrega. Las altas, ediciones y bajas funcionales se probaron con persistencia SQLite aislada. En la base local solo se hicieron recorridos de lectura y apertura/cancelación de formularios, además del inicio de sesión normal.

## Verificación realizada

- Referencia previa: 45 pruebas backend de atención/asignaciones/FUA y 62 pruebas frontend de Admisión/FUA aprobadas antes de la entrega.
- Backend completo: **850 pruebas unitarias aprobadas**.
- Frontend completo: **484 pruebas aprobadas y una omitida existente**, usando `npm test -- --maxWorkers=2`. La primera ejecución bajo carga agotó el tiempo de tres pruebas; la ejecución completa con dos trabajadores pasó sin aumentar sus límites.
- Comprobación de tipos: `npm run type-check -- --force` aprobada. La lectura transitoria de un archivo de prueba desapareció al reconstruir sin caché; no se eliminaron fuentes para resolverla.
- Compilación de producción aprobada. Se conserva el aviso previo de Vite por el tamaño de algunos paquetes.
- ESLint y Ruff del alcance modificado aprobados. Detector de interfaz sin hallazgos.
- Revisión en vivo como ADMIN: listado de establecimientos, detalle de sede, áreas independientes, alta contextual de consultorio con sede/área precargadas y edición de paciente sin acciones clínicas.
- Revisión de escritorio y móvil de 390 × 844, con apertura/cancelación del formulario de establecimiento. La configuración nueva usa controles táctiles y colores de texto legibles.

El servidor local se dejó iniciado en segundo plano en `127.0.0.1:8000` tras dejar de responder al retomar la sesión.

## Capturas

- `audits/admin-establecimientos-escritorio-20261022.png`
- `audits/admin-establecimientos-movil-20261022.png`
- `audits/admin-establecimiento-formulario-movil-20261022.png`
- `audits/admin-sede-areas-escritorio-20261022.png`
- `audits/admin-sede-areas-movil-20261022.png`
- `audits/admin-areas-escritorio-20261022.png`
- `audits/admin-areas-movil-20261022.png`

## Límites deliberados

La organización territorial superior y la edición de parámetros de FUA no se incorporan al formulario general del establecimiento. Sus referencias y valores actuales se conservan. La compatibilidad histórica del backend se mantiene; este cambio de navegación no elimina ni reclasifica consultorios antiguos.
