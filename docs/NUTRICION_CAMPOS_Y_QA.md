# Nutrición: captura por grupo y conservación histórica

Implementación y verificación: 9 de octubre de 2026 (Lima).

## Qué cambió

La atención mantiene sus mediciones y cálculos del servidor. Ahora admite datos
complementarios opcionales en `valoracion_nutricional`, y devuelve la evaluación
persistida en `evaluaciones_nutricionales`. El cliente no decide los resultados
calculados ni el estado de envío.

| Bloque | Captura y persistencia |
| --- | --- |
| Identidad | Documento, sufijo opcional, nombres, nacimiento, sexo, historia clínica y familiar congelados por atención. El sufijo también está en la ficha del paciente. |
| Organización y territorio | Establecimiento, IDEESS/RENAES, DISA, red, microred, provincia, distrito, localidad y seguro tomados del catálogo/ficha al atender. Se mantienen los valores ausentes. |
| Laboratorio | Hb y fecha del resultado juntas; Hb corregida **registrada**, método/referencia, altitud y hematocrito. No se aplica una fórmula nueva de corrección. |
| Infantil/adolescente | JUNTOS, PIN, CRECER; controles CRED, sachets, consejerías, sesiones, visitas; institución, nivel, grado, turno, matrícula, sección y aula. |
| Adulto/adulto mayor | Medidas e indicadores calculados existentes; P65, VL, CP y Pending como valores de origen opcionales. |
| Gestante | Semana gestacional y estado de ganancia de peso registrado, además de peso pregestacional, tipo de embarazo y demás mediciones obstétricas existentes. |
| Puérpera | Grupo diferenciado; conserva mediciones maternas y laboratorio sin admitir semana gestacional actual. |
| Valoración | Interpretación profesional separada de los indicadores calculados automáticamente. |
| Trazabilidad | Estado de exportación, fechas y constancia manual auditada de un envío realizado por otro canal. |

El grupo materno tiene prioridad sobre la edad. Fuera de grupos maternos,
los campos infantiles se habilitan para menores de 18 años y los de adultos
desde los 18. Esto no sustituye los rangos clínicos propios del motor nutricional.
La API rechaza los campos complementarios que no aplican; estas reglas pertenecen
al contrato del backend porque la captura complementaria ya no aparece en
admisión. `null`, `false` y `0` no son equivalentes.

## Pantallas

- Ficha y registro del paciente: sufijo documental opcional.
- Admisión/nueva atención: una sola sección compacta de valoración nutricional.
  La tabla cambia por grupo: P/E, T/E y P/T para niños/adolescentes; IMC y Dx IMC
  para adultos; IMC, Dx IMC y ganancia de peso para gestantes; e IMC y Dx IMC
  para puérperas. El IMC materno prioriza el pregestacional; si falta, muestra el
  IMC disponible. No muestra captura de laboratorio ni códigos del formato legado.
- Detalle: historia familiar/documento al momento de atender, valoración guardada,
  la misma tabla por grupo, resultados e interpretación; descarga de revisión y
  registro de constancia.
- FUA: su copia inmutable conserva los indicadores y diagnósticos del grupo y los
  muestra en el resumen. Solo se sobreimprime el IMC en la posición ya existente
  del formulario referencial; no se inventaron casillas oficiales para P/E, T/E,
  P/T, diagnóstico o ganancia de peso.
- Pantallas estrechas: menú plegable mediante un botón con estado accesible.

Los componentes `NutritionRecordSummary` (lectura histórica) y
`NutritionExportPanel` (descarga y constancia) permanecen en el detalle. La captura
complementaria se retiró de admisión para conservar la sección original
`clinical-section--nutrition`, de acuerdo con la referencia entregada. Las guías
Vue e Impeccable orientaron esta simplificación; no se hizo un rediseño de marca.

## Contrato de exportación, no integración oficial

`POST /api/v1/atenciones/{id}/nutricion/exportacion` produce
`IPRESS_NUTRICION_REVISION_V1`, JSON con `trama_oficial: false`, atención completa,
proyección de nombres legados y equivalencias pendientes. Descargar deja la
evaluación en `EXPORTADO`, **no** marca `Enviado`.

`POST /api/v1/atenciones/{id}/nutricion/envio` recibe
`{"constancia": "referencia verificable"}`. Exige una exportación previa y deja
constancia manual auditada. No conecta con SIS/SIEN. Repetir la misma constancia
es idempotente; otra constancia para un envío ya registrado produce conflicto.
Ambas operaciones verifican permisos, ámbito y atención activa.

El usuario confirmó que no dispone de catálogos para P65, VL, CP, Flag o
SufijoDocumento ni de la especificación receptora. Por ello:

- Se guardan como códigos de origen sin inventar su significado.
- Los códigos territoriales/documentales no se anuncian como homologados.
- PPG se proyecta provisionalmente desde peso pregestacional y se señala que
  requiere confirmación con el receptor.
- No hay transmisión oficial, aceptación automática ni certificación de trama.

## Migración y datos existentes

Revisión `20261008_0029_nutrition_fields`, desde
`20261007_0028_delivery_date`: agrega columnas anulables a pacientes,
atenciones y evaluaciones nutricionales. No rellena los históricos con datos
actuales, no recalcula resultados, no transforma ceros en nulos y no modifica
el archivo Access de origen.

En la base local habitual `sistema_salud_ipress` se aplicó la revisión y se
comprobaron las huellas de **todas las columnas originales** antes y después:
16 pacientes, 10 atenciones y 4 evaluaciones sin cambios. `alembic check` no
detectó diferencias pendientes respecto del ORM.

El recuento del hallazgo original sobre Access no describe necesariamente esta
base MySQL. Un puntaje Z igual a cero puede ser legítimo; por sí solo no demuestra
ausencia de cálculo. Se conserva lo almacenado. Los cálculos nuevos usan el
motor existente, con sus resultados/no-aplicabilidad persistidos por atención.

Los históricos sin `contexto_clinico` siguen siendo consultables, pero no se
reconstruyen ni se exportan como si tuvieran una copia histórica completa.
La ampliación no importa nuevamente registros del Access.

Para otras instalaciones: respaldar la base, detener escrituras y ejecutar
`alembic upgrade head` desde el entorno del proyecto. No hacer downgrade en una
base con información nueva: el downgrade elimina las columnas agregadas.
El ensayo de downgrade se realizó exclusivamente en una base desechable.

El auxiliar `tests/e2e/apply_local_nutrition_migration.py` es de uso local:
sin argumentos solo inspecciona; `--apply` exige exactamente la revisión anterior
y compara huellas de datos. No es un sustituto del respaldo de despliegue.

## QA reproducible

No se crearon pacientes ficticios en la base habitual. Las pruebas escribieron
solo en bases nuevas con prefijo `ipress_test_*`.

```powershell
.venv/Scripts/python.exe -m pytest tests/unit --no-cov -q
.venv/Scripts/python.exe tests/e2e/run_nutrition_mysql.py
```

El segundo comando crea una base local nueva con nombre aleatorio y verifica:
preservación de registros de revisión 0028, upgrade, downgrade/upgrade, coherencia
ORM y pruebas HTTP/MySQL. Nunca recibe el nombre de una base existente. La suite
de integración desmonta el esquema de prueba al terminar; no elimina bases.

Resultados backend: **371 pruebas unitarias y 92 de integración aprobadas**.
La matriz nueva cubre 60 combinaciones: 6 perfiles × 5 documentos × 2 modalidades,
con historia clínica, historia familiar, actualización posterior del paciente,
lectura del historial, exportación, persistencia de cero/No y cálculos aplicables.
También cubre accesos denegados, cancelación, reversión de escrituras inválidas,
constancia idempotente y lectura de históricos incompletos.

Desde `frontend`:

```powershell
npm.cmd test -- --maxWorkers=1 --testTimeout=60000
npm.cmd run build
```

Resultados frontend: **261 pruebas aprobadas y 1 omitida**. TypeScript y la
compilación de producción pasaron. En esta máquina se ejecutó la suite con un
solo trabajador y mayor margen de tiempo; las ejecuciones concurrentes habían
provocado tiempos de espera. Los componentes y auxiliares nuevos pasaron ESLint;
los archivos Python nuevos pasaron Ruff. Persisten hallazgos de estilo anteriores
en otros archivos, que no se reformatearon masivamente.

Para el navegador, preparar una base **nueva** con
`tests/e2e/audit_admission.py setup ipress_test_admission_<nombre_unico>` y servir
esa misma base con `serve` en el puerto 8001. El escenario utiliza el establecimiento,
consultorio y profesional ficticios de ese auxiliar. Después, desde `frontend`:

```powershell
$env:NUTRITION_E2E='1'
npx.cmd playwright test --config playwright.nutrition.config.ts
```

Playwright usa Edge y un frontend aislado en el puerto 5174. **3 recorridos
aprobados**: niño de 3 años, gestante y puérpera; guardado real en MySQL, recarga,
historial, copia FUA, descarga JSON y constancia externa ficticia. Los tres casos
también comprueban el menú móvil y ausencia de desbordamiento horizontal a 390 px.
Capturas locales: `tests/e2e/evidence_nutrition_20261008/`.

Revisión visual independiente: se corrigió la compresión de enlaces del menú
móvil, se capturó abierto y se verificaron visibilidad y foco del enlace al
historial. Veredicto final del revisor: `ship` para esa corrección, resuelta.
La revisión de documentación confirmó que los componentes nuevos conservan
los estilos existentes; no se crearon ni reemplazaron documentos de identidad
visual. La revisión no equivale a una auditoría completa de accesibilidad del
sistema ni a homologación clínica.

## Límites de esta entrega

- Hbc y estado de ganancia de peso son datos registrados por el profesional,
  no nuevos diagnósticos automáticos ni protocolos clínicos homologados.
- La exportación es individual y para revisión; la integración oficial exige
  obtener y validar la especificación del receptor.
- No se atribuye una historia familiar/territorial anterior a los registros que
  nunca la guardaron.
- Se conservan advertencias previas de dependencias de pruebas y de tamaño del
  paquete principal del frontend; no se hizo una actualización masiva de librerías.
