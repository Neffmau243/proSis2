# Consultorios: corrección aplicada y validación

Se conserva el flujo de trabajo clínico de la organización con tres selectores, en este orden:

1. **Consultorio**: muestra la jerarquía y agrupa las opciones dentro del mismo selector.
2. **Servicio / especialidad**: ofrece únicamente los servicios habilitados del consultorio.
3. **Profesional**: muestra profesionales asignados y vigentes para la fecha de atención.

El área asistencial se resuelve internamente desde el consultorio. No exige un cuarto campo ni otro paso al médico. Su configuración pertenece al módulo administrativo.

## Cambios aplicados

- Migración `20261013_0033_office_hierarchy`: añade área y servicios configurables, conserva IDs e historial. Se respaldaron los consultorios antes de aplicarla localmente; permanecen 42 consultorios y 372 asignaciones.
- Servicios agrupados según `Esp_*` de ETLSIS. Medicina habilita Medicina General, DANT, Pediatría y Ginecología. Se conservan los códigos generales para los registros/clientes existentes.
- Las actividades deduplicadas por el ETL, como Visita Domiciliaria, mantienen su pertenencia a varias áreas cuando el origen lo confirma.
- Catálogos compartidos exponen padre, ruta, área, servicios y disponibilidad de la jerarquía.
- Los subconsultorios heredan área, servicios y asignaciones de sus ancestros; pueden limitar los servicios habilitados. Se valida la especialidad base requerida al profesional.
- Se rechazan ciclos, padres de otra sede o área, bajas con descendientes activos y cambios que invaliden asignaciones vigentes/futuras.
- Los consultorios con ancestros inactivos o servicios explícitamente deshabilitados quedan fuera del selector clínico.
- Admisión y Laboratorio usan los mismos contratos. Cambiar consultorio o fecha actualiza los profesionales; después del guardado se bloquea la edición del contexto.
- Configuración presenta el árbol de consultorios y diferencia área de servicios. Los diálogos se adaptan al ancho móvil.

## Verificación

- Backend: **406 pruebas unitarias aprobadas**.
- MySQL: **32 pruebas de integración aprobadas** en bases nuevas y desechables. Incluyen guardado médico, herencia, ciclos, incompatibilidades, vigencias y servicios deshabilitados.
- Frontend: suite completa **303 pruebas aprobadas, 1 omitida**; tras retirar el selector adicional, **28 pruebas de las vistas afectadas aprobadas**.
- Compilación de producción y comprobación de tipos aprobadas. Ruff y lint de los archivos modificados aprobados. El detector de interfaz no informó hallazgos.
- Cuenta real `medico.demo` en `localhost:8000`: autenticación, catálogo de servicios de Medicina y selección de Laboratorio/profesionales verificados sin crear datos clínicos.
- Guardado desde navegador: cuenta médica de una copia temporal aislada, paciente ficticio y subconsultorio de prueba. Se confirmó el mensaje de guardado, el historial y el bloqueo de controles, también en móvil.
- La revisión automática rechazó crear registros ficticios en la base local y consultar identificadores del registro de pacientes. La prueba completa se realizó en la copia temporal, con limpieza automática de servidor y base.

Las capturas de QA corresponden a datos ficticios y al entorno temporal, no a una atención real del establecimiento.

## Datos que necesitan validación organizacional

El ETL aporta áreas y actividades, pero no una distribución fiable de salas físicas ni asignaciones reales por sede. Se conservó la distribución heredada para evitar retirar accesos basándose en suposiciones. Los responsables deben confirmar las ubicaciones y asignaciones reales; el módulo permite configurarlas con las nuevas validaciones.
