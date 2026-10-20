# Refactorización del backend: cambios y comprobaciones

Fecha: 20/10/2026. Implementación del [plan acordado](PLAN_REFACTOR_BACKEND_FLUJO_ACTUAL_20261020.md).

Actualización posterior: [ampliación de pruebas y medición de cobertura](COBERTURA_BACKEND_100_20261020.md). Los resultados siguientes corresponden al cierre inicial de la refactorización.

## Qué cambió

| Pieza | Resultado |
| --- | --- |
| Pacientes | `PatientService` coordina los casos de uso y sus transacciones. Las reglas de datos maestros, responsables y riesgos están en `patient_data.py`, `patient_responsible.py` y `patient_risk.py`. |
| Atenciones | `AttentionService.create` conserva el orden del guardado; delega contexto, validación de asignaciones, valoración nutricional y construcción de entidad. |
| Acceso | `ClinicalAccessService` comparte identidad y ámbito, conservando reglas distintas para pacientes, lectura, anulación, documentos y exportación. Las consultas de identidad/asignaciones y los predicados SQL de visibilidad también se comparten. |
| Snapshots | `AttentionContextLoader` prepara las relaciones necesarias. Un contexto tipado construye el JSON histórico con las funciones anteriores; la proyección preparada ejecuta cero consultas SQL. |
| Nutrición | `NutritionAssessmentService` reutiliza las reglas existentes para vista previa y guardado. El resolutor de edad está separado de la configuración administrativa de grupos etarios. |
| Origen de riesgos | `AttentionOriginReader` consulta únicamente los campos históricos y de autorización necesarios; ya no llama al servicio completo de atenciones ni carga todos sus hijos. |
| Exportación | `NutritionExportService` es independiente. Compone repositorios y acceso; el mapper conserva la proyección legada y la precisión decimal. |

Las firmas públicas de pacientes y atenciones permanecen iguales. Se conservaron adaptadores privados pequeños donde los consumidores/pruebas actuales los utilizan. Ningún colaborador nuevo confirma ni revierte transacciones: esa responsabilidad permanece en el caso de uso público.

Como señal secundaria de tamaño, la clase `PatientService` pasó de 1.060 a 625 líneas y de 42 a 21 métodos. `AttentionService.create` pasó de 170 a 105 líneas. Estas cifras comparan las clases/métodos mediante AST, sin contar imports y otros adaptadores del archivo.

## Flujos que se conservaron y comprobaron

- Alta, edición parcial, bajas, documento, residencia, seguro/SIS, responsables y riesgos del paciente.
- Vista previa frente a valores persistidos, nutrición infantil/escolar/adulta/adulto mayor/gestación/puerperio, modalidades y documentos admitidos por los contratos actuales.
- Actor de registro distinto del profesional seleccionado; asignación por sede, consultorio, especialidad y fecha.
- ADMIN + PROFESIONAL con vínculo activo mantiene acceso clínico. ADMIN solo conserva las restricciones clínicas anteriores.
- Referencia sin profesional/consultorio, origen y números con ceros iniciales, lectura, historial y anulación por su autor cuando corresponde.
- FUA, certificados, referencias y restricciones de anulación con documentos vigentes.
- Exportación, confirmación manual, repetición de una constancia y conflicto con una constancia diferente.
- Historial rápido de cinco y acceso paginado a registros anteriores, incluido el desempate por ID cuando coinciden las fechas.

Se inyectaron fallos reales después de escribir detalles, evaluación nutricional y auditoría. Una sesión MySQL independiente confirmó que no quedaron atenciones, hijos, cambios de condición ni auditorías parciales. El PATCH del paciente previamente confirmado permaneció guardado. También se verificó rollback de los cambios de estado/auditoría de exportación y confirmación manual.

La comparación estructural confirma que OpenAPI y las firmas públicas indicadas no cambiaron. Todos los archivos de `app/domain`, `fua_print.py` y `nutrition_context.py` coinciden byte por byte con la copia tomada antes de empezar. No hay migraciones ni modificaciones de esquema en esta entrega.

## Validación ejecutada

| Verificación | Resultado |
| --- | --- |
| Backend completo con MySQL desechable y cobertura | 671 pruebas aprobadas; 91,36 % de cobertura, mínimo original 90 %. |
| Regresión transaccional reforzada posterior | 9 pruebas aprobadas; incluye dos nuevos casos de fallo de exportación/confirmación y detalles clínicos reales en rollback. Cobertura global: 91,36 %. |
| Casos únicos del backend cubiertos entre ambas ejecuciones | 673 aprobados: 497 unitarios y 176 de integración. |
| Navegador, referencia real | 1 prueba aprobada en Chromium contra una API/base nuevas; verificación adicional del snapshot en MySQL. |
| Navegador, FUA/calibración | 6 pruebas aprobadas: impresión, PDF, referencia visual, SIS, geometría histórica e importación de calibración. |
| Compilación de interfaz y TypeScript | Aprobadas. Vite conserva el aviso de tamaño de algunos paquetes. |
| Interfaz completa con cobertura | 399 aprobadas y 1 omitida. Se mantuvieron y cumplieron todos los umbrales configurados. |
| Cobertura de utilidades/composables | Líneas: 98,18 % / 98,59 %; ramas: 93,25 % / 89,37 %; funciones: 99,2 % / 100 %. |
| Calidad Python | `ruff check app tests migrations --select F` aprobado; módulos nuevos comprobados con las reglas completas de Ruff. |
| Contratos y cambios de formato | OpenAPI/sources clínicos comparados con copia anterior; `git diff --check` aprobado. |
| Servidor de trabajo | `localhost:8000/admision?patientId=14` respondió 200 y entregó el build actual; sus siete assets públicos respondieron correctamente. |

La cobertura global de interfaz fue 80,13 % de líneas. El proyecto exige mínimos por grupos de archivos, no un mínimo global para todas las vistas. La ejecución final limitó Vitest a dos workers: una corrida con más procesos concurrentes había agotado el tiempo de un formulario bajo carga; no se modificaron los tiempos máximos ni los umbrales.

Las primeras ejecuciones detectaron problemas previos a la extracción: expectativas de catálogo sin `tipo`, fechas de asignación incompatibles con una atención histórica, pruebas que suponían encontrar establecimientos dentro de la primera página, campos FUA retirados en la semilla y una expectativa escolar antigua en la interfaz. Se corrigieron las pruebas/datos o la semilla según correspondía, conservando el comportamiento clínico. La referencia inicial del backend fue 646 aprobadas y 6 fallidas, con 89,97 % de cobertura.

## Evidencia y reproducción

La carpeta `tmp/backend-refactor-20261020/` contiene las copias anteriores, los logs de las fases, `structural-checks.json`, la comparación OpenAPI, los logs de interfaz y evidencia de navegador. Los archivos de evidencia no contienen credenciales de la base.

Las integraciones se ejecutaron con `TEST_DATABASE_URL` dirigido exclusivamente a un esquema nuevo desechable. Las fixtures hacen downgrade/upgrade: se debe crear otro esquema de prueba para reproducirlas, nunca usar la base de trabajo. El arnés local valida el nombre temporal antes de limpiarlo. El runner de referencia crea y elimina su propia base/API.

Los esquemas temporales de esta ejecución ya fueron eliminados. La base de trabajo no se utilizó para las escrituras de prueba ni se migró. Los cambios locales que existían antes de esta tarea se conservaron.

Comandos principales:

```text
python tmp/backend-refactor-20261020/run_checks.py reset
python tmp/backend-refactor-20261020/run_checks.py final
python tmp/backend-refactor-20261020/run_checks.py phase-two tests/integration/test_mysql_refactor_contracts.py --cov-append
python tmp/backend-refactor-20261020/verify_contracts.py
python -m ruff check app tests migrations --select F

# Desde frontend:
npm run test:coverage -- --maxWorkers=2
npm run build
npm run test:e2e -- fua-print.spec.ts --workers=1

# Desde la raíz, con Chromium instalado/configurado:
python tests/e2e/run_referral_e2e.py --output tmp/backend-refactor-20261020/referral-e2e
```

El catálogo pequeño de consultorios, los índices, una nueva política de idempotencia y la respuesta posterior al commit permanecen fuera del alcance acordado. Estas pruebas dan evidencia de los casos cubiertos; no representan una garantía de ausencia absoluta de errores.
