# Ampliación de pruebas del backend

Fecha: 20/10/2026. Continuación de la [refactorización verificada](REFACTOR_BACKEND_RESULTADOS_20261020.md).

## Alcance

Se añadieron pruebas para los huecos identificados en consultorios, autenticación, validación de atenciones, responsables y mantenimiento. Después se completaron los caminos restantes de configuración, contratos, nutrición, pacientes, documentos, repositorios y arranque de la aplicación.

Los cambios de aplicación de esta entrega son únicamente comentarios de medición en dos declaraciones `Protocol`. No se modificaron fórmulas, permisos, consultas, transacciones, respuestas HTTP ni estructura de la base de datos. La comparación de AST confirma que el dominio clínico conserva su código ejecutable; OpenAPI y las firmas públicas de pacientes/atenciones siguen iguales.

## Qué cubren las pruebas nuevas

| Área | Casos añadidos |
| --- | --- |
| Autenticación y usuarios | Límite por origen, cuenta bloqueada, vencimiento de ventanas, bloqueo progresivo con tope, credenciales genéricamente rechazadas, limpieza tras un acceso válido, roles inexistentes, cambios de contraseña/versionado y fallos de commit. Las auditorías de login se comprueban sin contraseñas, IP ni nombre de usuario en claro. |
| Consultorios | Sede/especialidad/padre no disponibles, otra sede, ciclos, cambios de padre, servicios incompatibles, descendientes, bajas, asignaciones duplicadas/superpuestas, reemplazo de responsable, cierres inválidos y errores de integridad. |
| Atenciones y documentos | Fechas y estados inválidos, recursos que desaparecen, profesional inactivo, conflictos de FUA/certificado/referencia y protección de la numeración ante una serie documental no disponible. |
| Responsables, pacientes y riesgos | Documentos incompletos, parentescos inválidos en llamadas internas, responsable principal único, nacimiento en 29 de febrero, riesgos iniciales, PATCH sin cambios, seguimiento abierto y fechas/catálogos inconsistentes. |
| Nutrición | Fecha anterior al nacimiento, sexo sin referencia, respuesta incompleta/no finita del calculador y talla sin incremento. Un resultado externo inválido nunca se publica como puntaje calculado. |
| Importador OMS | XLSX sintéticos con shared strings e inline strings; variantes de columna de edad; tablas mensuales completas; valores malformados, fraccionarios o incompletos; errores HTTP; hashes y origen de las seis tablas. Se usa transporte HTTP simulado y directorio temporal. |
| Herramientas de mantenimiento | Rechazo antes de abrir una conexión, confirmación oculta de contraseñas, identidades ya vinculadas, catálogos ausentes, simulación/aplicación de reparaciones, conservación de valores reales, idempotencia y rollback/cierre ante errores. Las operaciones destructivas del reset se sustituyen en sus pruebas unitarias. |
| Repositorios MySQL | Totales de catálogos sin filtro, etnias, profesional sin requisito de especialidad, consultorios inactivos, fechas acotadas de asignación, ciclos existentes, inclusión explícita de pacientes inactivos, relaciones y bloqueo de anulación por certificado vigente. |
| Arranque y archivos | API sin interfaz/CORS, build sin carpeta assets, archivos públicos, rutas reservadas, rechazo de archivos fuera del build y propagación de dependencias internas faltantes. |

Las entradas de servicio inválidas que el DTO HTTP normalmente rechaza se prueban también cuando corresponde, porque existen llamadores internos y datos históricos. No se debilitaron los DTO para alcanzar esas rutas.

## Cómo se mide el 100 %

Antes de marcar las declaraciones de interfaces, la medición acumulada llegó a **100 % de sentencias ejecutables y 99,97 % global**, con dos únicos arcos pendientes:

- `ClinicalProtocolValidator.validate`, en `app/domain/clinical.py`.
- `AuditWriter.record`, en `app/services/patient.py`.

Ambos son contratos de tipado con cuerpo `...`, sin implementación de validación ni persistencia. Se marcaron **solo esas declaraciones** con `pragma: no branch`; sus implementaciones concretas siguen incluidas y probadas. No se excluyeron archivos, validaciones, rutas de error ni herramientas de mantenimiento. El mínimo del proyecto permanece en 90 %.

La evidencia anterior a estas dos anotaciones se conserva en `tmp/backend-refactor-20261020/coverage100-raw-before-interfaces.log`. Esta distinción es parte del resultado y evita presentar como caso de negocio una llamada artificial a una interfaz vacía.

## Ejecución y evidencia

La ejecución completa desde cero terminó con **915 pruebas aprobadas, ninguna fallida ni omitida**, en 360,14 segundos:

| Medición | Resultado |
| --- | --- |
| Pruebas unitarias | 728 aprobadas. |
| Integración con MySQL descartable | 187 aprobadas. |
| Sentencias | 6.667 de 6.667; **100 %**. |
| Ramas según la política explicada arriba | 1.312 medidas; ninguna pendiente ni parcial; **100 %**. |
| Cobertura global | **100,00 %**. |
| Archivos de aplicación | 116 con cobertura completa. |
| Autenticación, consultorios, validación de atenciones y responsables | **100 %** en cada módulo. |
| Herramientas de mantenimiento | **100 %** en todos los módulos de `app/scripts`. |
| Calidad | Reglas completas de Ruff y formato en los archivos de prueba nuevos/ampliados; comprobación F en `app tests migrations`; `git diff --check`. |

Respecto de los 673 casos anteriores, se añadieron **242 casos**. El mínimo de cobertura sigue en 90 %; no se rebajó ningún control para aprobar la suite.

Evidencia del cierre:

- Log: `tmp/backend-refactor-20261020/coverage-final-pytest.log`.
- [Reporte HTML navegable](../output/backend-coverage-100-20261020/index.html).
- [Datos completos de cobertura](../output/backend-coverage-100-20261020/coverage.json).
- [Verificación exacta y excepciones de tipado](../output/backend-coverage-100-20261020/verification.json).
- Comparación de contratos y dominio: `tmp/backend-refactor-20261020/coverage100-structural.log`.

El verificador comprobó `percent_covered == 100.0` en el JSON de los 116 archivos, cero sentencias/ramas pendientes y exactamente las dos marcas de tipado declaradas. No se tomó un porcentaje redondeado como prueba del 100 %.

Los esquemas temporales ya fueron eliminados. La base de trabajo y las tablas OMS reales del proyecto no se modificaron con estas pruebas.

Archivos principales de pruebas añadidas:

- `tests/unit/test_authentication_abuse.py` y `test_user_security_boundaries.py`.
- `tests/unit/test_office_service.py` y `test_clinical_validation_boundaries.py`.
- `tests/unit/test_import_who2007.py`, `test_create_professional_user.py`, `test_repair_patient_workflow.py` y `test_seed_recovery.py`.
- `tests/unit/test_patient_relationship_boundaries.py`, `test_clinical_persistence_failures.py` y `test_nutrition_failure_boundaries.py`.
- `tests/unit/test_input_configuration_boundaries.py`, `test_catalog_configuration_boundaries.py` y `test_application_boot_boundaries.py`.
- `tests/integration/test_mysql_repository_boundaries.py`.

Se amplió además `tests/unit/test_fua_print.py` con una atención UTC que debe imprimir la fecha local de Lima del día anterior.

Para reproducir en el entorno local preparado:

```text
python tmp/backend-refactor-20261020/run_checks.py reset
python tmp/backend-refactor-20261020/run_checks.py coverage-final
python -m coverage report --precision=2
python -m coverage json -o tmp/backend-refactor-20261020/coverage100-final.json
python tmp/backend-refactor-20261020/verify_contracts.py
python tmp/backend-refactor-20261020/run_checks.py cleanup
```

La suite también se ejecuta con `python -m pytest` si `TEST_DATABASE_URL` apunta a otro esquema MySQL nuevo y descartable. Las fixtures realizan downgrade/upgrade; nunca se debe utilizar la base de trabajo.

La cobertura demuestra qué líneas/ramas recorrieron las pruebas. No equivale a haber enumerado todas las combinaciones de entradas ni garantiza ausencia absoluta de errores.
