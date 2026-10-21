# Importación de pacientes ETLSIS de Arequipa

Ejecución local: 20 de octubre de 2026, hora de Lima.

Se importó exclusivamente el padrón compatible con el esquema y las reglas
actuales. No se aplicaron migraciones ni se modificó la estructura de `pacientes`.

## Resultado en la base del proyecto

| Concepto | Cantidad |
| --- | ---: |
| Registros en `Pacientes` de Access | 73.209 |
| Pacientes nuevos importados | 28.938 |
| Pendientes de depuración o conciliación | 44.251 |
| Fuera del ámbito o distrito no resuelto | 20 |
| Pacientes existentes antes / después | 24 / 28.962 |
| Atenciones existentes antes / después | 44 / 44 |
| Atenciones de pacientes importados | 0 |
| Distritos con pacientes importados | 19 |
| Importación registrada | `importaciones_legado.id = 1` |

Arequipa significa aquí la **provincia**, UBIGEO `0401`: se pudieron resolver sus
29 distritos contra el catálogo actual. El filtro usa residencia del paciente.
Los 19 distritos del resultado son aquellos con pacientes que superaron todas
las reglas, no una modificación del catálogo territorial.

## Correspondencia y decisiones

| Origen Access | Destino / tratamiento |
| --- | --- |
| `Codclie` | `codclie_legacy`, sin reutilizarlo como PK |
| `N°_DNI` | Tipo `DNI` y `numero_documento`; ocho dígitos conservados como texto |
| `Historia_Clinica` | `historia_clinica`, conserva ceros |
| `Historia_Familiar` | `historia_familiar` si cumple prefijo activo y formato actual |
| Apellidos y nombres separados | Columnas equivalentes, sin reconstruir desde nombre completo |
| `Fecha_nacimiento` | Fecha válida obligatoria, no futura |
| `Fecha_inscripcion` | Se conserva si es válida y no anterior al nacimiento |
| `Sexo` | Catálogo activo `M` / `F` cuando existe equivalencia |
| `Distrito` | `Provincia` de origen y UBIGEO vigente comprobados entre sí |
| `Localidad` | Catálogo dentro del distrito si coincide; en otro caso conserva texto válido |
| `Dirección` | `direccion` |
| `Establecimiento` | Nombre único del catálogo Access → RENAES → ID actual activo |
| `Seguro` | Nombre equivalente del catálogo activo; desconocido queda `NULL` |
| `Arequipa_040`, `Arequipa_2`, `Arequipa_SIS` | Campos SIS si su formato es válido, tipo/número completos y seguro del régimen SIS |
| `Condicion` | Solo archivo original; una gestación histórica no acredita estado actual |
| Campos sin correspondencia verificada | Solo archivo original |

No se inventan documento, nacimiento, responsable, teléfono, etnia, sufijo
documental ni profesional de registro. Los pacientes nuevos están activos por
el valor predeterminado del modelo. Las columnas sin dato fiable quedan `NULL`.

Los datos opcionales incompatibles —por ejemplo historia familiar o afiliación
SIS incompleta— quedan en el original archivado, no se fuerzan al contrato
operativo. La fecha `2016-01-01` se conserva con incidencia porque podría ser una
fecha de carga masiva. Los textos dañados o demasiado largos en identidad,
historia clínica o domicilio bloquean la promoción, sin truncarlos.

Se excluyen todos los miembros de grupos con DNI, código legacy o combinación
de nombre/nacimiento repetidos. La duplicación se analiza en **todo el origen**,
antes del filtro territorial. También se comprueban los pacientes ya existentes,
incluidos inactivos; no se fusionan ni actualizan automáticamente. Doce filas
del origen coinciden con documentos ya presentes y quedan pendientes.

La regla de responsable del sistema considera la edad en la fecha de inscripción,
o en la fecha de referencia si aquella falta. Quien era menor en esa fecha queda
pendiente cuando el origen no acredita responsable, aunque ahora sea adulto.
Este importador no interpreta `Anexo*` como parentescos ni convierte pacientes
de `Pacientes_ref` en identidades del padrón.

## Trazabilidad y repetición

`importaciones_legado` identifica la fuente por SHA-256 y versión del importador.
Cada paciente creado tiene una fila en `registros_legado` con número de fila
original, huella, incidencias, JSON original completo y correspondencia al ID
autoincremental. El JSON escapado conserva incluso datos que no serían válidos
en el JSON nativo de MySQL. Se registra auditoría por paciente y por lote.

Las únicas tablas modificadas son `pacientes`, `registros_legado`,
`importaciones_legado` y `auditoria`. Todos los cambios del lote se confirman en
una sola transacción. Un bloqueo MySQL evita dos importadores simultáneos; las
restricciones únicas siguen protegiendo frente a otras escrituras concurrentes.

La repetición reconoce filas ya importadas por fuente, posición, huella y destino;
no sobrescribe posteriores cambios del paciente. Si cambia su documento o código
legacy y deja de concordar con la trazabilidad, el caso queda pendiente. Esta
herramienta no implementa un borrado automático ni debe revertirse con Alembic.

## Uso

Desde la raíz del proyecto, simulación sin escrituras:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_legacy_patients --as-of 2026-10-20
```

Carga de todos los aptos:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.import_legacy_patients --as-of 2026-10-20 --apply
```

`--limit 100` permite un piloto determinista. `--report` guarda solo recuentos e
incidencias agregadas. `--source` y `--snapshot` admiten rutas explícitas. Las
rutas predeterminadas son `Data_base.mdb` y `etlSis/private/ace-source`.

El comando solo permite MySQL local y `ENVIRONMENT=development`. Verifica la
huella del MDB y de todos los archivos del snapshot ACE. No necesita ejecutar
el ETL antiguo ni su SQL. El snapshot y el respaldo contienen datos personales:
permanecen en las rutas locales excluidas de Git. No incluirlos en commits.

## Verificación realizada

- Respaldo completo y restauración comprobados por huellas de contenido de las
  46 tablas en una base nueva de ensayo.
- Simulación sin cambios; fallo inyectado después de insertar pacientes y antes
  de archivar: reversión íntegra comprobada.
- Carga de 28.938 pacientes en la copia; segunda ejecución con cero inserciones
  y exactamente las mismas huellas de todas sus tablas.
- Carga confirmada en la base del proyecto; comparación posterior: los 24
  pacientes anteriores y las 42 tablas ajenas conservaron su contenido.
- Lectura y serialización de muestras con `PatientService`, sin atenciones,
  riesgos ni responsables fabricados.
- Simulación posterior en la base real: 28.938 `YA_IMPORTADO`, cero por insertar.
- 93 pruebas unitarias aprobadas, incluidas 38 nuevas pruebas del importador y
  regresiones de pacientes, SIS y actualización parcial. Ruff aprobado.

Informes locales agregados: `output/etl-pacientes-arequipa-20261020/`:
`plan.json`, `verification.json`, `importacion.json`, `post-verificacion.json` y
`reconciliacion.json`. El informe de ensayo conserva ruta y SHA-256 del respaldo
anterior a la carga; la copia de prueba permanece disponible para revisión.

Las incidencias de cada regla se superponen: no sumarlas como pacientes únicos.
Los informes describen la ejecución del 20/10/2026; no garantizan que los datos
personales del origen o su afiliación histórica estén vigentes hoy.
