# Sistema de Salud IPRESS

Backend REST para el esquema `sistema_salud_ipress`, construido con **Python 3.12**, **FastAPI**, **SQLAlchemy 2** y **MySQL 8**. La estructura conserva la separación conceptual de Spring Boot, sin trasladar mecánicamente sus convenciones a Python. El repositorio también incluye la SPA de operación en [`frontend/`](frontend/).

Documentación relacionada:

- [frontend/README.md](frontend/README.md) — la aplicación Vue 3: módulos implementados, barra lateral, estructura y verificación.
- [GUIA_FRONTEND_RUTAS.md](GUIA_FRONTEND_RUTAS.md) — contrato HTTP por pantalla, permisos, catálogos y vacíos del API.
- [docs/REVISION_FLUJO_Y_ARQUITECTURA.md](docs/REVISION_FLUJO_Y_ARQUITECTURA.md) — revisión del 17/09/2026: flujo real, mejoras aplicadas y deuda técnica.

## Arranque rápido (desarrollo)

Requisitos: Python 3.12 con `requirements.txt` instalado, MySQL local y Node
22.18+ de la rama 22 o 24.12+ (ver `frontend/package.json`). Detalle completo en [Puesta en marcha local](#puesta-en-marcha-local).

```bash
# terminal 1 — backend, desde la raíz del repo
python -m app.scripts.bootstrap_database              # crea la BD y aplica migraciones
python -m app.scripts.create_admin --username admin   # primer ADMIN (pide la contraseña)
uvicorn app.main:app --reload
python -m uvicorn app.main:app --reload
python -m uvicorn app.main:app --reload

# terminal 2 — frontend
cd frontend && npm install && npm run dev
cd frontend && npm run dev
```

Abrir <http://localhost:5173> e ingresar con el ADMIN creado. La API queda en
<http://127.0.0.1:8000/api/v1> y su documentación en
<http://127.0.0.1:8000/docs>.

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| `admin` | `74028519` | ADMIN (base local de este repo) |
| `medico.demo` | `18594027` | PROFESIONAL (cuenta de pruebas vinculada a un profesional real) |



Las credenciales son exclusivamente para la base local desechable; nunca se
reutilizan fuera de desarrollo.

> **Estado de la base de este repo**: quedó **limpia** — los catálogos reales de
> Arequipa (migraciones `20260926_0020_real_catalogs`,
> `20260926_0021_real_professionals` y `20260926_0022_specialty_codes`), el
> `admin`, la cuenta clínica `medico.demo` vinculada a un profesional real y
> **62 profesionales reales con su especialidad y asignación a consultorio**, y
> los **13 pacientes reales del origen** (los de `Data_base.mdb`). No hay
> pacientes ficticios. `seed_demo_data` ya **no** crea catálogos `DEMO_*`:
> resuelve las sedes y los profesionales sembrados por las migraciones y solo
> agrega el cohorte ficticio (o, con `--real-only`, solo los pacientes reales).

## Arquitectura

El flujo de una escritura es:

```text
Router / Controller  →  Service (caso de uso)  →  Repository  →  SQLAlchemy Model  →  MySQL
        │                       │                       │
        └── Pydantic schemas ───┴── Mappers ────────────┘
```

Los modelos nunca se devuelven desde HTTP. Los routers se limitan a autenticar, validar el contrato Pydantic y llamar a un servicio. Los servicios contienen reglas, límites transaccionales y orquestación; los repositorios únicamente ejecutan persistencia y consultas.

| Concepto Spring Boot | Equivalente aquí |
| --- | --- |
| `@Entity` | Modelo ORM SQLAlchemy (`app/models`) |
| `Repository` | Repositorio SQLAlchemy (`app/repositories`) |
| DTO | Schema Pydantic (`app/schemas`) |
| Mapper | Función/clase mapper explícita (`app/mappers`) |
| `@Service` | Servicio de caso de uso (`app/services`) |
| `@RestController` | `APIRouter` de FastAPI (`app/controllers`) |
| `@ConfigurationProperties` | `pydantic-settings` (`app/core/config.py`) |
| `@ControllerAdvice` | Handlers FastAPI (`app/exceptions`) |
| JUnit / Mockito | pytest / unittest.mock |

La organización es una arquitectura por capas pragmática: carpetas transversales para hacer visibles los límites de cada capa y módulos de dominio cohesionados dentro de ellas. Las políticas puras de edad y validación clínica viven en `app/domain`, para que no dependan ni de HTTP ni de SQLAlchemy.

## Esquema MySQL y revisión de migraciones

La API usa la conexión de `.env` (`MYSQL_*` o `DATABASE_URL`). El head del
código es `20260916_0010_locality`: normaliza localidad y conserva el distrito
como catálogo de ubigeo. El ORM declara 39 tablas funcionales;
`alembic_version` es una tabla técnica adicional.

Compruebe cada instalación con `alembic current`, `alembic heads` y
`alembic check`. El head del repositorio no demuestra que una base desplegada
esté migrada. `TEST_DATABASE_URL` se reserva para integración en MySQL desechable.

| Dominio | Tablas MySQL |
| --- | --- |
| Catálogos | tipos_documento, sexos, seguros, especialidades, prestaciones, cie10, modalidades_atencion, grupos_etarios, grupos_riesgo |
| Organización | disa, redes, microredes, ubigeos, establecimientos, consultorios, consultorio_profesionales |
| Seguridad | profesiones, profesionales, profesional_especialidades, roles, usuarios, usuario_roles, limites_inicio_sesion, auditoria |
| Pacientes | pacientes, paciente_anexos_legacy, paciente_codigos_externos, paciente_grupos_riesgo, paciente_responsables |
| Clínica | atenciones, atencion_diagnosticos, atencion_prestaciones, evaluaciones_nutricionales, vigilancia_sien |
| Documentos | fua, certificados, certificado_prestaciones, referencias, documento_series |

~~~text
disa → redes → microredes → establecimientos → consultorios
                                           └→ pacientes → atenciones → FUA / certificado / referencia
profesionales ↔ especialidades; profesionales ↔ consultorios
usuarios ↔ roles; pacientes ↔ grupos_riesgo
~~~

La FK compuesta de certificados obliga a que el profesional firmante sea el
mismo de la atención. documento_series controla la numeración por tipo,
establecimiento y período.

### Catálogos sembrados por migración

El ámbito de los datos reales es Arequipa y no depende del volcado `etlSis/`
(que es solo la guía de origen y **no se entrega**): los valores viven horneados
en las migraciones.

| Migración | Siembra |
| --- | --- |
| `20260919_0015_patient_sis` | catálogo de etnias (MINSA) |
| `20260923_0017_insurance_plans` | planes SIS y Sanidad |
| `20260924_0018_sis_localities` | 29 distritos (`ubigeos`) + 475 localidades |
| `20260924_0019_eess_catalog` | 6 sedes con RENAES válido |
| `20260926_0020_real_catalogs` | DIRESA `040`, 4 redes, 47 microredes, 33 especialidades (código `origen:codigo`) y 42 consultorios (6 sedes × 7 áreas) |
| `20260926_0021_real_professionals` | 7 profesiones, 62 profesionales (código = `id` de origen), su especialidad principal y una asignación vigente a cada consultorio del área |
| `20260926_0022_specialty_codes` | normaliza a mayúsculas los códigos de `especialidades`, como exige la API |

Los 32 placeholders `EE.SS. DEL DPTO.` y las filas de texto libre del origen se
ignoran a propósito. Las filas de `consultorios` son inferidas: el origen solo
lista áreas de servicio.

`pacientes.profesional_registro_id` apunta al profesional que registró al
paciente o cambió su sede: alimenta el ámbito asistencial descrito en RB-02 y
no se expone como campo editable del PATCH.

## Estructura

```text
app/
├── api/                 # ensamblaje de routers
├── controllers/         # borde HTTP/FastAPI
├── core/                # settings, DB, seguridad y dependencias
├── domain/              # políticas de negocio puras (autorización, edad, nutrición)
├── exceptions/          # excepciones y handlers globales
├── mappers/             # ORM -> DTO, sin serializar entidades directamente
├── models/              # mapeo SQLAlchemy completo del esquema MySQL
├── repositories/        # acceso a datos, sin reglas de negocio
├── schemas/             # contratos Pydantic de entrada/salida
├── scripts/             # bootstrap, admin inicial, semillas, reinicio y reparación local
├── services/            # casos de uso y transacciones
└── main.py
migrations/
└── versions/            # revisiones Alembic (fuente ejecutable del esquema)
tests/
├── unit/
└── integration/
frontend/                # SPA Vue 3 + TypeScript (ver frontend/README.md)
```

## Operaciones HTTP (56)

| Dominio | Operaciones | Éxito |
| --- | --- | --- |
| Salud | GET /health | 200 |
| Autenticación | GET /auth/usuarios-activos; POST /auth/login; PUT /auth/me/password | 200, 204 |
| Usuarios | POST /usuarios; PUT /usuarios/{id}/roles; PUT /usuarios/{id}/password; DELETE /usuarios/{id} | 201, 200, 204 |
| Pacientes | GET y POST /patients; GET, PATCH y DELETE /patients/{id}; responsables y riesgos POST/PATCH | 200/201 |
| Catálogos | 14 GET bajo /catalogos para identidad, clínica, establecimientos, consultorios, profesionales y ubigeos | 200 |
| Grupos etarios | GET y PUT /configuracion/grupos-etarios | 200 |
| Profesionales | GET y POST /configuracion/profesionales; GET, PATCH y DELETE /{id}; PUT /{id}/especialidades | 200/201 |
| Consultorios | GET y POST /configuracion/consultorios; GET, PATCH y DELETE /{id}; asignaciones GET, POST y PATCH de cierre | 200/201 |
| Atenciones | GET de lista, búsqueda e individual; POST de registro, vista previa de indicadores nutricionales y anulación | 200/201 |
| Documentos | POST /documentos/fua, /certificados y /referencias | 201 |

Los contratos de entrada y salida viven en app/schemas. Toda respuesta de error
usa el sobre definido por los handlers globales e incluye X-Request-ID.

## Puesta en marcha local

1. Cree un entorno virtual e instale dependencias:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Use el `.env` existente y complete sus variables `MYSQL_*` y secretos de JWT. El flujo normal usa esa misma MySQL; no requiere un environment ni una base de pruebas aparte.
3. Inicialice la base y aplique las migraciones:

   ```powershell
   python -m app.scripts.bootstrap_database
   ```

   El comando crea la base MySQL si falta, sin borrar una existente, y ejecuta
   `alembic upgrade head`. No ejecute `schema_mysql_salud.sql`: es solo una
   referencia del diseño.
4. Cree el primer administrador (el comando solicita la contraseña sin mostrarla):

   ```powershell
   python -m app.scripts.create_admin --username admin
   ```

   Para probar la admisión **sin** cargar pacientes ficticios, cree solo la
   cuenta clínica vinculada a un profesional real y con asignación vigente:

   ```powershell
   python -m app.scripts.create_professional_user --username medico.demo
   ```

   Para tener pacientes reales con los que probar la admisión, sin cargar el
   cohorte ficticio, use el modo `--real-only` (13 pacientes del origen):

   ```powershell
   python -m app.scripts.seed_demo_data --real-only
   ```
5. Opcionalmente cargue el cohorte ficticio para probar todos los flujos de la
   API. Este comando es idempotente: crea solo los registros que no existan y no
   elimina ni sustituye datos existentes. Úselo únicamente en desarrollo local.
   La semilla **no** crea catálogos `DEMO_*`: resuelve las sedes reales
   (`20260924_0019_eess_catalog`), el consultorio de medicina y un profesional
   real (`20260926_0021_real_professionals`) ya sembrados por las migraciones.

   ```powershell
   python -m app.scripts.seed_demo_data
   ```

   Al terminar muestra los IDs creados o verificados. La colección Postman los
   descubre automáticamente, por lo que no hace falta copiarlos a un environment.
   La semilla vincula la cuenta `medico.demo` a un profesional real y carga 14
   pacientes ficticios con DNI, distritos y seguros variados, responsables para
   cada menor, antecedentes de riesgo, 5 atenciones históricas con signos
   vitales, indicadores nutricionales calculados por el servidor y un FUA, un
   certificado y una referencia; todas las atenciones y documentos se crean a
   través de `AttentionService` y `DocumentService`, así que respetan las mismas
   reglas que la API (requiere `alembic upgrade head` al día).

6. Ejecute la API:

   ```powershell
   uvicorn app.main:app --reload
   ```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs` y la especificación OpenAPI en `/openapi.json`.

## Evolución del esquema

Alembic es la única fuente ejecutable del esquema. bootstrap_database crea la
base si falta y ejecuta la migración pendiente sin borrar ni vaciar datos.
schema_mysql_salud.sql es solo una referencia de diseño y no debe ejecutarse
para inicializar la instalación.

Para una migración futura, modifique el modelo, genere una propuesta, revísela
y aplíquela:

~~~powershell
alembic revision --autogenerate -m "descripcion_del_cambio"
alembic upgrade head
alembic check
~~~

No edite revisiones que ya hayan sido aplicadas. Los datos semilla y las reglas
de negocio requieren migraciones o servicios deliberados, no autogeneración.

Convenciones que debe respetar cada revisión:

- El id de revisión debe tener **32 caracteres o menos**: `alembic_version.version_num`
  es `VARCHAR(32)` y un id más largo falla recién al sellar la versión, después
  de que MySQL ya aplicó el DDL.
- MySQL no hace DDL transaccional. Igual que 0007, 0008 y 0009, consulte
  `sa.inspect(op.get_bind())` antes de cada `add_column`, `create_index` o
  `create_foreign_key` para que reintentar sea seguro.
- `tests/unit/test_migration_contract.py` valida el head y el total de tablas
  del ORM: actualícelo en la misma migración que los cambia.

### Reinicio local completo

Para una instalación local que puede descartarse, detenga primero Uvicorn y
ejecute este único comando. El script elimina **solo** la base definida en
`.env`, aplica todas las migraciones y carga las semillas ficticias con cuentas
listas para Postman:

```powershell
python -m app.scripts.reset_demo_database --demo-credentials --confirm-delete
```

Las credenciales son exclusivamente para esa BD desechable: `admin` /
`74028519` y `medico.demo` / `18594027` (este reinicio **sí** vuelve a cargar
los catálogos `DEMO_*` y los pacientes ficticios). El script no
puede ejecutarse en producción. Si prefiere una contraseña propia, omita
`--demo-credentials` y use el modo interactivo o `--generate-password`.

No se puede ejecutar si `ENVIRONMENT=production` o `prod`. No use este comando
en una base con información real.

Para una corrida completa sobre la MySQL ya configurada use solamente
[`postman/IPRESS_API_flujo_feliz.postman_collection.json`](postman/IPRESS_API_flujo_feliz.postman_collection.json).

### Reparación de datos de residencia

Cuando una base antigua quedó con pacientes sin distrito, sin localidad o sin
seguro, y con el catálogo ``ubigeos`` nombrado por distritos vecinos, este
comando repara el catálogo y completa las fichas. Fabricar domicilios es una
decisión de desarrollo, por eso **no** es una migración: se niega a correr con
`ENVIRONMENT` distinto de `development` e informa cada cambio. Sin `--apply`
solo simula, y es idempotente: una segunda ejecución no cambia nada.

```bash
python -m app.scripts.repair_patient_data           # simulación
python -m app.scripts.repair_patient_data --apply   # aplica
```
Cubre 54 de las 56 operaciones publicadas (faltan el selector de usuarios y la
vista previa nutricional), genera y captura los IDs/tokens propios y
fuerza sus variables de colección para que un Environment de Postman activo no
pueda reemplazar URL, credenciales ni IDs. Antes de correrla, edite
`adminUsername` y `adminPassword` dentro de la colección si su cuenta ADMIN
local no usa las credenciales demo. No ejecute el reinicio destructivo anterior
para usar esta colección.

Las altas responden `201` y los cambios de contraseña `204`, ambos estados de
éxito; la colección valida todo el rango `2xx` y detiene la corrida al primer
error. El `PUT` de grupos etarios reenvía el estado leído para no sustituir la
configuración clínica actual. Las bajas al final son lógicas: se conservan las
atenciones, documentos y auditorías de prueba por trazabilidad.

La asignación de un consultorio se prueba en este orden: el GET de
/configuracion/consultorios/{office_id}/profesionales devuelve [] al crear un
consultorio porque todavía no existe una fila en consultorio_profesionales;
luego el POST crea el vínculo y un segundo GET verifica que el profesional
aparece. La respuesta vacía inicial es correcta, no un error.

## Roles

El sistema opera con dos roles separados por responsabilidad:

- `ADMIN`: gestiona usuarios, profesionales, consultorios, asignaciones,
  configuración y registro de pacientes mediante el API. La SPA aún tiene
  módulos administrativos pendientes. No puede registrar/anular atenciones
  ni emitir FUA, certificados o referencias clínicas.
- `PROFESIONAL` (rol del médico o profesional de salud): debe estar vinculado
  a un profesional activo. Puede buscar y trabajar pacientes dentro de sus
  establecimientos asignados, de su relación asistencial o de los que él mismo
  registró o trasladó; registra, consulta
  y anula solo sus propias atenciones, y emite documentos únicamente para
  ellas. No puede dar de baja pacientes ni administrar usuarios/configuración.

Las asignaciones vigentes de consultorio se administran por `ADMIN` y son un
requisito para registrar una atención. Los cambios de roles, la baja lógica y
un cambio/restablecimiento de contraseña se aplican inmediatamente: las
sesiones JWT anteriores quedan invalidadas cuando cambia la contraseña.

## Flujo clínico longitudinal

En la SPA: iniciar sesión → buscar o registrar paciente → seleccionarlo →
**Iniciar admisión**. `/admision?patientId=<id>` reúne guardados explícitos:

| Acción | Contrato | Resultado |
| --- | --- | --- |
| Crear paciente | `POST /api/v1/patients` | Nuevo paciente con responsables/riesgos iniciales cuando corresponda. |
| **Guardar cambios** en “Datos del paciente” | `PATCH /api/v1/patients/{id}` | Un payload con los campos modificados; conserva los omitidos. |
| Guardar madre/responsable o riesgo | `POST`/`PATCH` de `responsibles` y `risk-groups` | Cada relación se guarda desde su formulario y conserva el historial. |
| **Guardar atención** | `POST /api/v1/atenciones` | Nuevo acto clínico con los datos del paciente ya guardados. |

Se editan identidad, historia clínica/familiar, nacimiento, sexo, distrito,
localidad, dirección, establecimiento, seguro, teléfono, inscripción y condición.
Edad y grupo etario son derivados. El borrador se conserva si falla el PATCH,
se puede descartar y bloquea el POST de atención mientras tenga cambios.
Un fallo del POST no revierte un PATCH confirmado. La ruta antigua
`/pacientes/:id/editar` redirige a Admisión.

Admisión exige `ATENCION_CREAR`; su editor verifica `PACIENTE_EDITAR`.
Un ADMIN sin permiso clínico conserva el PATCH en la API pero no tiene acceso
al editor de datos maestros en la SPA. Esta diferencia figura como pendiente
en la revisión de arquitectura.

`pacientes` guarda identidad y datos maestros; cada `POST /atenciones` inserta
una fila nueva vinculada al paciente, con fecha, profesional, sede,
consultorio, signos vitales, edad e historia clínica de ese acto. No existe un
endpoint que sobrescriba una atención: solo puede anularse de forma lógica y
con justificación. El historial se consulta con `GET /atenciones/busqueda` o
`GET /atenciones?paciente_id=...`, limitado al ámbito asistencial del
profesional.

Los indicadores nutricionales derivados los calcula el servidor
(`app/domain/nutrition.py`) y el cliente nunca los envía: el IMC sale de peso y
talla, y P/E, T/E y P/T son los puntajes Z OMS 2006 (WAZ/HAZ/WHZ) para menores
de 60 meses con sexo registrado. Son indicadores, no diagnósticos: la
clasificación clínica y las etiquetas del snapshot (`evaluaciones_nutricionales`)
siguen siendo responsabilidad del profesional. La API ofrece el mismo cálculo sin persistir mediante
`POST /atenciones/indicadores-nutricionales/vista-previa`; el servicio y el
composable frontend existen, pero la vista actual aún no conecta esa vista previa.
El perímetro abdominal y la valoración gestacional no tienen referencia
automática conectada.

Los rangos etarios se conservan internamente en meses completos para la
precisión clínica, pero el API devuelve además `edad_minima`, `edad_maxima` y
`rango_edad_legible` en años y meses para que el frontend los muestre sin hacer
conversiones propias.

## Reglas que protege el backend

- Las credenciales se almacenan únicamente como hashes bcrypt y los roles se validan por acción.
- En producción se rechazan secretos JWT plantilla; las semillas ficticias se bloquean fuera de `ENVIRONMENT=development`.
- Los inicios de sesión quedan auditados sin almacenar contraseñas, usan límite persistente por huella HMAC y bloqueo progresivo de cuenta.
- Un usuario cambia su propia contraseña con la clave actual; `ADMIN` puede restablecer otra cuenta activa. Nunca se permite retirar el último `ADMIN` activo.
- Un menor requiere responsable activo; solo puede tener uno principal activo.
- El documento de identidad es único, se valida fecha de nacimiento y se comprueba que los catálogos estén activos.
- Los periodos de riesgo no se pueden solapar.
- Los grupos etarios se configuran sin solapes y se resuelven en el servidor; el cliente no puede imponerlos.
- Una atención valida paciente, ámbito, consultorio, sede, profesional, especialidad, vigencia y signos clínicos antes de grabarse; su anulación es lógica, auditada y se bloquea si conserva documentos vigentes.
- La emisión de FUA se pre-valida y se mantiene la garantía única de MySQL. Las operaciones relevantes incluyen su auditoría dentro de la misma transacción.

Los rangos clínicos y las políticas de numeración son configurables o puertos explícitos, no constantes de SQL. Las reglas detalladas se consolidan a continuación.

## Reglas funcionales detalladas

### RB-01: autenticación y autorización

- Por requerimiento del equipo, las contraseñas tienen exactamente ocho dígitos
  ASCII y el login ofrece una lista pública de nombres de usuarios activos.
  Esta decisión expone nombres de cuenta y reduce el espacio de claves;
  el límite de intentos y el bloqueo siguen activos.
- Las contraseñas se comparan con bcrypt; nunca se almacenan ni devuelven en
  texto plano.
- Solo ADMIN crea, desactiva o asigna roles. Un PROFESIONAL activo y vinculado
  opera exclusivamente su atención y documentos.
- Cada token se contrasta con usuario activo, roles y versión de credenciales.
  El cambio o restablecimiento de contraseña invalida sesiones anteriores.
- El login tiene límite persistente, bloqueo progresivo y auditoría sin
  contraseña ni IP en claro. No se puede desactivar ni quitar el rol al último
  ADMIN activo.

### RB-02: pacientes y responsables

- La combinación tipo de documento y número de documento es única; la fecha de
  nacimiento no puede ser futura y los catálogos deben existir y estar activos.
- Un menor requiere al menos un responsable activo y solo puede tener un
  responsable principal activo. Los parentescos admitidos son madre, padre y
  tutor.
- Un PROFESIONAL solo puede leer o editar pacientes de su ámbito asistencial:
  una sede con asignación vigente, una atención no anulada propia o un
  `pacientes.profesional_registro_id` a su favor. Los períodos del mismo grupo
  de riesgo no pueden superponerse.
- Registrar un paciente o cambiar su establecimiento de registro solo exige que
  el establecimiento exista y esté activo (`establecimiento_registro_id`); no se
  exige una asignación vigente del profesional en esa sede. El servicio guarda
  entonces al profesional autenticado como autor del registro
  (`pacientes.profesional_registro_id`), para que no pierda el acceso al
  paciente que acaba de registrar o trasladar. Un ADMIN o un llamador interno
  no modifican ese vínculo.

### RB-03: grupos etarios

- La unidad canónica es mes completo. Todo grupo activo necesita edad mínima,
  no puede haber solapes, solo uno puede quedar sin máximo y la cobertura
  continua se valida cuando la IPRESS la exige.
- La configuración inicial aplica estas etapas: NIÑO de 0 a 11 años,
  ADOLESCENTE de 12 a 17, JOVEN de 18 a 29, ADULTO de 30 a 59 y ADULTO MAYOR
  desde los 60 años. Los límites se almacenan en meses completos.
- Al crear una atención, el servidor calcula el grupo por fecha de nacimiento
  y fecha de atención. El cliente nunca impone el grupo etario. La atención
  conserva ese grupo como dato histórico y la condición maestra del paciente
  se sincroniza con la etapa vigente; GESTANTE y PUERPERA tienen prioridad
  cuando corresponden al grupo de atención. RECIEN NACIDO se conserva durante
  los primeros 28 días.

### RB-04: consultorios y profesionales

- El consultorio y el profesional deben estar activos; el consultorio pertenece
  al mismo establecimiento de la atención.
- Debe existir una asignación vigente en consultorio_profesionales para la
  fecha de atención. Si el consultorio exige especialidad, el profesional debe
  tenerla.
- Solo puede existir un responsable vigente por consultorio. La asignación
  nueva no puede solaparse con otra del mismo profesional y consultorio.

### RB-05: atención clínica

- La atención valida paciente, sede, profesional, consultorio, modalidad,
  especialidad, grupo etario, asignación y signos vitales antes de confirmar.
- Peso, talla, perímetro y edad son una foto histórica de la atención; el
  cliente no puede imponer IMC, P/E, T/E ni P/T, que el servidor calcula con la
  referencia OMS 2006 y trata como indicadores y no como diagnóstico.
- Las atenciones no se eliminan físicamente. La anulación exige justificación,
  auditoría y se bloquea si existen documentos vigentes.

### RB-06: documentos clínicos

- Solo el propietario profesional de una atención atendida puede emitir FUA,
  certificado o referencia.
- FUA es único por atención. Las series de FUA, certificados y referencias se
  reservan dentro de la misma transacción.
- Un certificado debe estar firmado por el profesional de su atención; una
  referencia debe tener origen, destino, tipo, motivo y estado válidos.

### RB-07: transacciones y auditoría

- Toda escritura relevante valida, persiste y audita antes de confirmar la
  transacción. Un fallo hace rollback.
- auditoria guarda actor, acción, fecha, registro y foto antes/después, sin
  password_hash ni secretos.
- Pacientes, usuarios, profesionales, consultorios y documentos usan bajas
  lógicas cuando aplica; no se hace DELETE físico sobre el historial clínico.

## Pruebas

```powershell
pytest   # incluye cobertura y umbral mínimo (pyproject.toml)
python -m ruff check app tests migrations --select F
```

> **Windows con Git Bash:** MSYS convierte valores que parecen rutas en las
> variables de entorno, por lo que `API_V1_PREFIX=/api/v1` llega a Python como
> `C:/Program Files/Git/api/v1` y la suite no recolecta. Use PowerShell, o desde
> Git Bash exporte `MSYS2_ENV_CONV_EXCL='API_V1_PREFIX'` antes de ejecutar
> `pytest`.

La suite tiene tres bloques y una sola orden:

| Bloque | Qué verifica | Necesita MySQL |
| --- | --- | --- |
| `tests/unit` | Reglas de dominio, esquemas, seguridad, guardas de los comandos operativos y el contrato de migraciones. | No |
| `tests/integration` | Router, controladores, servicios, repositorios y SQL real: alta/edición de pacientes, búsqueda, catálogos, flujo clínico, documentos y las consolas `create_admin`/`bootstrap_database`/`seed_demo_data`/`reset_demo_database`. | Sí |
| `frontend/tests` | Utilidades, servicios, composables, store, guardas y flujos montados con Vitest. | No |

La integración se activa con `TEST_DATABASE_URL` apuntando a una base
**desechable cuyo nombre incluya `test`**: la fixture aplica y revierte
migraciones (`downgrade base` → `upgrade head`) antes y después de la sesión, y
aborta si el nombre no cumple el guard. Sin esa variable, esas pruebas se
omiten y la cobertura cae por debajo del umbral.

```bash
# MySQL local desechable, sin tocar la base de desarrollo
export TEST_DATABASE_URL='mysql+pymysql://root:clave@127.0.0.1:3306/sistema_salud_ipress_test'
pytest
```

La cobertura se exige en `[tool.coverage.report]` (`fail_under`) y se mide con
ramas. Hoy la suite completa ronda el 92% en backend.

En `frontend/`, ejecute `npm test` (o `npm run test:coverage`), `npm run
lint:check` y `npm run build`. CI levanta **MySQL 8** como servicio, exporta
`TEST_DATABASE_URL` y aplica los mismos umbrales en ambos lados. El control Ruff
de CI está limitado a reglas `F`; no equivale a comprobar toda la política de
estilo. Resultados y límites en [la revisión de arquitectura](docs/REVISION_FLUJO_Y_ARQUITECTURA.md).

`tests/unit/test_migration_contract.py` es la red de seguridad del esquema:
falla si el head de Alembic o el número de tablas del ORM dejan de coincidir con
lo esperado. Actualícelo dentro de la misma migración que cambie cualquiera de
los dos.
