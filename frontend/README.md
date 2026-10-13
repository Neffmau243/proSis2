# IPRESS Frontend

Aplicación de operación de IPRESS con Vue 3, TypeScript, Composition API,
Vite, Pinia, Vue Router y Element Plus en español. Contraste de implementación:
17/09/2026. El backend FastAPI está en la raíz del repositorio.

- [Arranque y reglas del backend](../README.md).
- [Contratos y rutas HTTP](../GUIA_FRONTEND_RUTAS.md).
- [Revisión de flujo, mantenibilidad y escalabilidad](../docs/REVISION_FLUJO_Y_ARQUITECTURA.md).

## Arranque

Requisitos: backend iniciado y Node `^22.18.0 || >=24.12.0`.

```powershell
cd frontend
npm ci
npm run dev
```

Vite sirve normalmente [localhost:5173](http://localhost:5173) y reenvía
`/api` a `http://127.0.0.1:8000`. Si el puerto está ocupado puede elegir otro.
Para una API en otro origen, configure `VITE_API_BASE_URL` en `.env.local`,
incluyendo una sola vez `/api/v1`, y configure CORS en el backend.

Para desplegar en **un solo servidor** no use `npm run dev`: ejecute
`npm run build` y deje que el backend FastAPI sirva `frontend/dist` desde el
mismo puerto de Uvicorn (ver [README raíz](../README.md)). En ese modo el
cliente usa `/api/v1` del mismo origen por defecto y CORS deja de ser necesario.

Cuentas de la base local desechable:

| Usuario | Contraseña | Uso |
| --- | --- | --- |
| `admin` | `74028519` | Registro/configuración administrativa. |
| `medico.demo` | `18594027` | Flujo clínico; se crea con `create_professional_user` (o `seed_demo_data`). |

La base de este repositorio quedó **limpia**: catálogos reales de Arequipa,
`admin` y 62 profesionales reales con asignación a consultorio, sin pacientes
ficticios. `seed_demo_data` ya **no** crea catálogos `DEMO_*`: usa las sedes y
los profesionales de las migraciones y solo agrega 14 pacientes ficticios. No
sobrescribe cuentas existentes. Los
identificadores de pacientes, consultorios y profesionales dependen de la base;
búsquelos en la aplicación, no suponga que un ID fijo pertenece siempre al mismo
paciente.

## Flujo de trabajo

1. Iniciar sesión. El selector lista y filtra nombres de usuarios activos.
   La contraseña tiene exactamente ocho dígitos. Si falla el directorio,
   se permite escribir el usuario. Un 429 se informa sin reintentar en bucle.
2. Buscar en **Base de datos**, seleccionar una fila o crear un paciente.
   La búsqueda tiene debounce, páginas y carga adicional con `has_more`.
3. Pulsar **Iniciar admisión** en el paciente seleccionado.
4. Corregir **Datos del paciente** y pulsar **Guardar cambios**.
5. Completar consultorio, profesional y datos clínicos; pulsar **Guardar atención**.
6. Consultar el detalle, emitir documentos o anular cuando las reglas lo permitan.

La ficha `/pacientes/:id` conserva datos, responsables, riesgos e historial.
No hay pantalla independiente de edición de datos maestros: los enlaces antiguos
`/pacientes/:id/editar` redirigen a `/admision?patientId=:id`.

## Admisión: PATCH y POST

En `/admision?patientId=<id>`, `admission-workbench__patient` contiene el editor.

| Acción visible | Petición | Comportamiento |
| --- | --- | --- |
| Escribir en los datos del paciente | Ninguna | Modifica un borrador local. |
| **Guardar cambios** | `PATCH /patients/{id}` | Envía juntos únicamente los campos modificados. |
| **Descartar cambios** | Ninguna | Restaura los datos guardados; no revierte operaciones ya confirmadas. |
| Guardar madre/responsable | `POST /patients/{id}/responsibles` o `PATCH .../{responsibleId}` | Guarda desde el diálogo del responsable. |
| Guardar periodo de riesgo | `POST /patients/{id}/risk-groups` o `PATCH .../{riskId}/{startDate}` | Conserva los periodos anteriores; permite cerrar/anotar uno existente. |
| **Guardar atención** | `POST /atenciones` | Crea una atención; no vuelve a enviar el PATCH del paciente. |

Todos los endpoints de esta tabla llevan el prefijo `/api/v1`.

Campos editables: historia clínica, historia familiar, tipo/número de documento,
fecha de nacimiento, apellidos, nombres, sexo, distrito por ubigeo, localidad,
dirección, establecimiento de registro, seguro, teléfono, fecha de inscripción
y condición. **Edad actual** y **Grupo etario** se calculan con el nacimiento
guardado; la edad y el grupo de la atención los determina el backend.

La madre es un responsable con parentesco `MADRE`; los riesgos son periodos
relacionados, no columnas del paciente. Se reutilizan sus formularios desde el
mismo panel, con guardado propio. Una edición de esas relaciones no borra un
borrador pendiente de datos maestros.

Se validan campos obligatorios, longitudes, fechas y distrito/localidad.
La API conserva la validación definitiva de duplicados, catálogos, permisos y
responsables para menores. Los fallos conservan lo escrito. Se bloquean doble
envío, guardar atención con cambios del paciente pendientes y salir del editor
sin guardar o descartar. La expiración de sesión puede llevar al login.

El establecimiento de registro solo cambia la sede inicial de la atención si
todavía no se eligió consultorio. Si ya se eligió, se conserva esa sede clínica.

## Pantallas y alcance real

| Ruta | Implementación actual |
| --- | --- |
| `/login` | Selector de usuarios, validación y sesión. |
| `/` | Lista de pacientes, búsqueda, selección, detalle y baja lógica por permiso. |
| `/pacientes/nuevo` | Alta con identidad, residencia, responsables y riesgos. |
| `/pacientes/:id` | Ficha y gestión de responsables/riesgos; historial según permiso. |
| `/admision?patientId=<id>` | Editor del paciente y alta de atención. |
| `/atenciones/nueva` | Pantalla oculta. Los enlaces con `patientId` válido abren Admisión; sin paciente vuelven a Base de datos. |
| `/atenciones` | Pantalla general oculta; redirige a Base de datos. El historial continúa en la ficha del paciente. |
| `/atenciones/:id` | Detalle, anulación, FUA, certificado y referencia. |
| `/cuenta/cambiar-contrasena` | Cambio de contraseña propia y cierre de sesión. |
| `/configuracion/usuarios` | Solo alta; la API no ofrece lista/detalle de usuarios. |
| `/configuracion/grupos-etarios` | Lectura y reemplazo de rangos completos. |
| `/configuracion/profesionales`, `/configuracion/consultorios` | Pantallas pendientes; sí existen APIs administrativas. |
| `/configuracion/auditoria` | Consulta de auditoría según permisos. |
| `/laboratorio` | Registro de atenciones en consultorios de laboratorio, búsqueda de pacientes, datos SIS, historial paginado y conteo diario por profesional. Reutiliza el flujo clínico y la impresión SIS de admisión. |

Laboratorio recibe `paciente_id` al abrirse desde un paciente seleccionado en Base de datos.
Requiere `PACIENTE_LEER`; guardar requiere `ATENCION_CREAR` y consultar el registro requiere
`ATENCION_LEER`. El filtro `consultorio_id` de `/atenciones/busqueda` se aplica tanto al
historial como al conteo, conservando el alcance de acceso del usuario. El conteo corresponde
a los turnos configurados en hora de Lima (07:00–13:00 y 13:00–19:00). La ficha permite
editar sus campos visibles con `PACIENTE_EDITAR`; usa el mismo borrador, PATCH y
validaciones de Admisión. «Guardar cambios» confirma la ficha y «Descartar» la restaura.
No se puede cambiar de paciente ni registrar una atención con cambios pendientes.
La edad se calcula desde el nacimiento. Al pasar a un seguro ajeno a SIS o vaciar
el seguro, se limpia la afiliación del borrador; «Sin seguro» y seguro sin registrar
se presentan sin campos SIS. HCI continúa disponible tras guardar la atención;
las impresiones SIS se habilitan exclusivamente para pacientes con seguro SIS.
La impresión utiliza exclusivamente la instantánea de una atención guardada.
Las órdenes de exámenes y los resultados siguen fuera de este flujo.

Laboratorio conserva los elementos de la captura del sistema anterior con la
estética actual de Admisión: paneles azul suave, tipografía de la aplicación,
controles Element Plus y acciones primaria/secundarias/salida. Mantiene los
grupos de documento y modalidad arriba, fecha/hora separadas, consultorio y
profesional en orden vertical y los cinco botones. El historial mantiene 10 registros por
página y separa los apellidos y nombres; usa la identidad de la instantánea
cuando está disponible. Estado y acceso al detalle permanecen en su pie.
Los números de referencia y contrarreferencia son identificadores de ingreso
de la atención, conservan ceros iniciales y no crean documentos de salida.
Imprimir HCI imprime el resumen de la atención guardada; FUA adicional imprime
un ejemplar del mismo FUA y no genera otra numeración. Observaciones continúa
disponible en su sección desplegable. En móvil los paneles se apilan.
El arnés `tests/laboratory-workspace-harness.html` usa únicamente datos sintéticos
y simula el guardado en memoria, sin consultar ni modificar pacientes reales.

Las búsquedas DNI, historia clínica similar y nombres usan `q` (mínimo dos
caracteres); historia clínica exacta usa `historia_clinica`. Historia familiar
continúa deshabilitada porque no hay filtro backend.

La vista clínica actual registra contexto, medidas y valoración nutricional
escrita. La API y los tipos soportan prestaciones y CIE-10, pero la vista de alta
no ofrece esos controles. El composable de vista previa nutricional existe,
aunque no está conectado a la vista actual. IMC y puntajes se calculan al
crear la atención y se muestran en historial/detalle.

**Imprimir S.I.S.**, **Otra consulta** y **FUA adicional** solo muestran un aviso
de función pendiente. Emitir documentos desde el detalle sí llama a la API,
pero no existe descarga/impresión persistida de esos documentos.

## Permisos

La fuente de permisos es el backend; menús, guard de rutas y botones los
consultan. `ADMIN` gestiona datos administrativos; `PROFESIONAL` atiende
únicamente dentro de su ámbito. El profesional elegido en el formulario viaja
en el POST y el servidor comprueba que corresponde al usuario autenticado.

Admisión requiere `ATENCION_CREAR` y el editor comprueba `PACIENTE_EDITAR`.
Actualmente ADMIN conserva permiso de PATCH en la API, pero no puede entrar
a Admisión ni editar datos maestros desde la SPA: pendiente de resolver como
decisión de flujo. La combinación ADMIN + PROFESIONAL también requiere revisar
la precedencia de roles en los servicios clínicos; no se debe asumir que la
unión de menús implica que todas las operaciones estén autorizadas.

## Organización y criterios de mantenimiento

| Pieza | Responsabilidad |
| --- | --- |
| `router/index.ts`, `layouts/AppLayout.vue` | Navegación, estructura y permisos de interfaz. |
| `stores/auth.ts`, `services/session-storage.ts` | Sesión reactiva y persistencia local. |
| `services/http.ts` | Axios, Bearer, errores normalizados y redirección por 401. |
| `services/*.ts` | Contratos TypeScript y llamadas a cada recurso HTTP. |
| `AdmissionPatientSummary.vue` | Formulario del paciente, estado de guardado y composición de relaciones. |
| `AdmissionPatientRelations.vue` | Madre, responsables y periodos; reutiliza los diálogos existentes. |
| `useAdmissionPatientEditor.ts` | Borrador, validación y ciclo del PATCH; persistencia inyectada para pruebas. |
| `useAdmissionPatientDetails.ts`, `useRemoteCatalog.ts` | Catálogos, etiquetas, búsqueda remota acotada y descarte de respuestas antiguas. |
| `utils/patientDraft.ts` | Lista de campos editables, diferencias y validaciones puras. |
| `AtencionNuevaView.vue` | Orquestación de paciente guardado y POST clínico; aún necesita dividir sus secciones grandes. |

Los datos fluyen por props y eventos tipados. El editor nunca modifica el
objeto del paciente recibido. Un `null` explícito vacía un campo opcional;
un campo omitido se conserva. Los valores calculados y las colecciones
relacionadas nunca se mezclan con el PATCH maestro.

Hay deuda adicional de paginación, sesión, errores y tamaño del bundle.
La barra lateral de 264 px todavía dificulta operar en móvil.
Consulte la revisión de arquitectura antes de considerar completada una
adaptación móvil o una validación de escalabilidad.

## Comandos y verificación

| Comando | Efecto |
| --- | --- |
| `npm run dev` | Desarrollo con recarga. |
| `npm test` | Suite completa (Vitest) una vez. |
| `npm run test:watch` | Suite en modo interactivo. |
| `npm run test:coverage` | Suite con cobertura y umbrales. |
| `npm run test:e2e` | E2E de navegador (Playwright) de la impresión FUA. |
| `npm run lint:check` | Oxlint + ESLint sin modificar archivos. |
| `npm run lint` | Oxlint + ESLint con correcciones. |
| `npm run type-check` | Comprobación TypeScript/Vue. |
| `npm run build` | Tipos y compilación de producción. |
| `npm run preview` | Sirve la compilación local. |
| `npm run format` | Formatea `src/` con Prettier. |

## Pruebas

Vitest con `happy-dom` y `@vue/test-utils`; no necesitan backend ni base de
datos. La configuración está en `vitest.config.ts` y los archivos en `tests/`:

| Archivo | Qué fija |
| --- | --- |
| `tests/patientEditor.test.ts` | Diferencias, borrado de opcionales, validación, un solo PATCH por guardado, reintento tras fallo y descarte. |
| `tests/patientSearch.test.ts` | Cada modalidad de búsqueda usa un único criterio y respeta los mínimos de la API. |
| `tests/services.test.ts`, `tests/http.test.ts` | Rutas, parámetros, payloads, Bearer, sobre de error y redirección por 401. |
| `tests/storeAuth.test.ts` | Sesión persistida, vencimiento, permisos y cierre de sesión. |
| `tests/composables.test.ts` | Paginación, búsqueda remota con descarte de respuestas antiguas, vista previa nutricional. |
| `tests/router.test.ts` | Guardas de navegación por sesión y permisos. |
| `tests/views/*.test.ts`, `tests/layouts/*.test.ts`, `tests/components/*.test.ts` | Flujos montados: login, búsqueda del padrón y acciones sobre el paciente seleccionado. |
| `tests/*.test.ts` (utilidades) | Edad por calendario, FUA impreso, SIS, contraseña y borrador del FUA. |

La cobertura se mide sobre `src/**` y se exige por capa en `vitest.config.ts`
(utilidades, servicios, composables, store, guardas y layout). Bajar de ese
umbral falla la ejecución. CI ejecuta lint, `test:coverage` y build del
frontend, además del job de backend con MySQL 8.

`vitest.config.ts` fija dos ajustes deliberados: `async-validator` se resuelve
al build ESM -el que usa el navegador- para que la validación de Element Plus
deje de resolver en silencio, y Element Plus se procesa con el resolvedor de
Vite. Sin ellos, `el-form.validate()` informaría éxito con campos vacíos.

### Pruebas de navegador (Playwright)

`npm run test:e2e` ejecuta `e2e/fua-print.spec.ts` en un Chromium real: monta el
arnés sintético de Vite, calibra la impresión FUA en milímetros, guarda la
geometría en `localStorage` y captura el documento que se enviaría a la
impresora (los datos del paciente, el tamaño de hoja `@page` y el aviso de que
no se imprime el fondo ni los controles). No usa backend ni datos reales.

Requiere un navegador de Playwright instalado (`npx playwright install
chromium`) o, si ya hay uno en caché, apuntar a su ejecutable con
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/ruta/a/chrome`. El servidor de Vite lo levanta
la propia configuración (`playwright.config.ts`).
