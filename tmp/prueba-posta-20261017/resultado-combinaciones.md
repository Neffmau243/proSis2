# Pruebas de combinaciones de admisión - 17/10/2026

## Resultado

Las combinaciones habituales y las validaciones ya implementadas pasaron, pero las pruebas exploratorias encontraron vacíos. No se considera validado el circuito clínico completo ni la integración oficial SIS. No se modificó código de la aplicación.

| Bloque | Resultado |
| --- | --- |
| Matriz API/MySQL existente | 212/212 comprobaciones satisfactorias |
| Rechazos adicionales, con comprobación de que no dejan una atención parcial | 15/15 satisfactorios |
| Exploraciones de compatibilidad de grupos y fechas obstétricas | 7 comportamientos documentados; requieren revisión, no se cuentan como éxitos |
| Pruebas visuales del sistema local | 14 comprobaciones: 13 satisfactorias y 1 observación de compatibilidad |
| Pruebas unitarias dirigidas | 112 aprobadas |

## Separación de datos

Las pruebas automáticas se ejecutaron con TestClient de FastAPI y MySQL real en una nueva base separada: `ipress_test_admission_20261017_combinaciones`. La preparación rechazaba reutilizar o borrar una base existente. Se ejecutaron las migraciones actuales y se crearon cuenta, consultorio y pacientes ficticios de prueba. No se reinició la base habitual ni se usaron pacientes reales.

La prueba visual utilizó `medico.demo` y al niño ficticio Prueba Lucero Mateo Simulado, DNI 99061017, paciente #17 del recorrido anterior. Solo se guardó una nueva atención en la base habitual: **#22**, modalidad **EMERGENCIA**, grupo general, profesional **ELSA GUILLEN TOCCAS**. La atención permaneció como ATENDIDO al volver a abrirla. No se emitió un número FUA adicional en esta ronda; se verificó el prellenado de impresión correspondiente a emergencia.

## Cobertura automática

La matriz cruzó cinco tipos de documento (CE, DE, DNI, OTRO y PAS), dos modalidades (ambulatoria y emergencia), sexos y edades de 1, 8, 14, 32 y 76 años en grupo general, y gestantes/puérperas de 16 y 32 años. Incluyó 140 escenarios con medidas completas, 60 con peso o talla faltantes y 12 rechazos de medidas o grupos inválidos.

Se contrastaron cálculo nutricional, IMC independiente, guardado, consulta individual, historial, persistencia MySQL y copia de datos para el FUA. Las comprobaciones no evalúan la suficiencia clínica del protocolo ni la conformidad oficial SIS.

Los 15 casos adicionales rechazados correctamente fueron:

- Atención futura y atención anterior al nacimiento.
- Fecha efectiva anterior a la atención y hora fin anterior a inicio.
- Presión sistólica inferior o igual a la diastólica.
- Temperatura y presión fuera de los límites del protocolo configurado.
- Consultorio de otra sede y profesional no asignado al consultorio.
- Grupo general con fecha de parto, gestante con fecha de parto y puérpera con fecha probable de parto.
- Diagnóstico CIE-10 inexistente y prestación inexistente.

En los 15 casos se comparó el número de atenciones antes y después de la solicitud: no quedó ninguna atención parcialmente creada.

## Prueba visual

Se comprobó el bloqueo de campos requeridos, peso de 501 kg, talla de 301 cm y fecha futura. Una fecha histórica sin asignación vigente limpió la selección del profesional. Enfermería mostró un catálogo de profesionales distinto a Medicina; al cambiar de consultorio se limpió el profesional anterior y se actualizó el servicio.

Se probaron transiciones de grupo general a Gestantes, luego a Puérperas y de vuelta al grupo general sin guardar esos grupos obstétricos en la base habitual. La vista intercambió los campos de fecha; al volver al grupo general recuperó los indicadores infantiles.

La atención #22 guardó peso 15 kg, talla 100 cm, PAB 50 cm, presión 90/60 mmHg y temperatura 36.6 °C. Mostró P/E, T/E y P/T como Normal y conservó EMERGENCIA en el prellenado del FUA. El botón de guardar quedó deshabilitado tras el éxito. Al reabrir el detalle se comprobaron modalidad y medidas, y que tipo de embarazo, peso pregestacional y fecha probable de parto estaban vacíos: no se arrastraron a la atención general.

## Hallazgos que impiden afirmar que todo está correcto

### Compatibilidad entre paciente y grupo obstétrico

La API aceptó y marcó ATENDIDO los siguientes casos ficticios, sin una advertencia o confirmación de contexto:

| Caso exploratorio | Respuesta | Atención en base aislada |
| --- | --- | --- |
| Adulto registrado con sexo masculino / Gestantes | 201 | 203 |
| Adulto registrado con sexo masculino / Puérperas | 201 | 204 |
| Niño de 3 años / Gestantes | 201 | 205 |
| Niña de 3 años / Puérperas | 201 | 206 |

La pantalla también permitió seleccionar Gestantes para el niño de 3 años de la prueba visual. Esa selección no se guardó en la base habitual. Debe definirse y validar la compatibilidad clínica por edad y contexto, con advertencias y manejo de excepciones apropiado; no se propone un bloqueo indiscriminado basado solo en el sexo registral.

### Coherencia de fechas obstétricas

Se guardó una puérpera con fecha de parto **01/01/2027** en una atención del **17/10/2026**, como ATENDIDO (atención aislada #208). Hace falta validar que una fecha de parto declarada no sea posterior a la fecha de atención.

También se aceptó una fecha probable de parto anterior a la atención (#207). Se documenta como caso para revisión de reglas/advertencias; no se clasifica por sí solo como inválido, ya que una fecha estimada vencida puede necesitar un tratamiento distinto a una fecha de parto real futura.

### Cierre de atención sin detalle clínico

La API permitió guardar como ATENDIDO una atención sin mediciones, diagnósticos ni prestaciones (#209 de la base aislada). Esto confirma el vacío señalado en el recorrido inicial: si el guardado de admisión no representa la consulta finalizada, debe distinguirse ese estado y validar los datos requeridos al completar la consulta. No todos los signos o medidas tienen necesariamente que ser obligatorios para todos los tipos de atención.

### Pendientes ya conocidos

No se corrigió la discrepancia entre el profesional seleccionado al guardar y el profesional de la cuenta al emitir documentos. Tampoco se volvió a probar la descarga PDF ni la impresión física en esta ronda.

## Evidencias y reproducción

- Matriz detallada: `../../tests/e2e/ipress_test_admission_20261017_combinaciones_matrix.json` desde la raíz del proyecto: `tests/e2e/ipress_test_admission_20261017_combinaciones_matrix.json`.
- Casos adicionales y respuestas: `combinaciones-extra.json`.
- Casos visuales: `combinaciones-ui.json`.
- Captura del FUA con modalidad emergencia: `emergencia-fua.png`.
- Script adicional: `verificar_combinaciones_extra.py` (los documentos de los pacientes son fijos para esta corrida; no reejecutar sobre la misma base sin adaptar esos identificadores).

Comandos ejecutados:

```powershell
.\.venv\Scripts\python.exe tests/e2e/audit_admission.py setup ipress_test_admission_20261017_combinaciones
.\.venv\Scripts\python.exe tests/e2e/verify_admission_matrix.py ipress_test_admission_20261017_combinaciones
.\.venv\Scripts\python.exe tmp/prueba-posta-20261017/verificar_combinaciones_extra.py
.\.venv\Scripts\python.exe -m pytest tests/unit/test_nutrition_preview_validation.py tests/unit/test_attention_service.py tests/unit/test_admission_validation_regression.py tests/unit/domain/test_nutrition.py tests/unit/domain/test_growth_reference.py -q --no-cov -p no:cacheprovider
```

Se observaron avisos de configuración/deprecación de pytest y Starlette/httpx; no causaron fallos de estas pruebas. No se midió cobertura global ni se afirma haber probado todas las combinaciones posibles.
