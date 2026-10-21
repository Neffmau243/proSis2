# Revisión del flujo de profesiones, áreas y especialidades

La prueba posterior realizada íntegramente en la interfaz real, desde Personal
hasta la atención 45 y el FUA de Cardiología, está documentada en
[E2E_PERSONAL_CARDIOLOGIA_20261021.md](E2E_PERSONAL_CARDIOLOGIA_20261021.md).
Lo que sigue corresponde a la revisión previa con un esquema temporal y un harness.

## Resultado de la prueba real

Se ejecutaron dos pruebas de integración contra un esquema MySQL temporal,
creado para esta revisión y eliminado al finalizar. Se utilizó el mismo backend,
migraciones, autenticación y controladores de la aplicación. No se modificaron
las fichas de la base de aplicación.

El recorrido verificado fue:

1. Crear una profesión de prueba relacionada con Nutrición.
2. Crear una especialidad de Nutrición clínica.
3. Crear un profesional con la profesión y la especialidad nuevas.
4. Crear un consultorio del área existente Nutrición.
5. Intentar asignar al profesional sin el área base: se rechazó con
   `PROFESIONAL_SIN_ESPECIALIDAD`.
6. Añadir el área Nutrición a la ficha, conservando la especialidad principal.
7. Asignar al profesional al consultorio: se aceptó.
8. Registrar una atención de Consulta nutricional con una cuenta de prueba
   vinculada a ese profesional: se aceptó.
9. Editar los nombres de la profesión, la especialidad y el área: sus códigos,
   IDs, vínculos y clasificación se conservaron. Consultorios mostró el nuevo
   nombre del área.

## Qué representa cada dato

| Dato | Función | Ejemplo |
|---|---|---|
| Profesional | La persona | Profesional de prueba |
| Profesión | Su formación registrada | Nutricionista |
| Especialidad | Una cualificación asignada a la persona | Nutrición clínica |
| Área | La habilitación base que exige el consultorio | Nutrición |
| Consultorio | El espacio de atención dentro de una sede | Consultorio de Nutrición |
| Servicio | La actividad registrada en una atención | Consulta nutricional o Canasta TBC |
| Cuenta | La identidad de acceso al sistema | Cuenta con rol PROFESIONAL |

Profesión y especialidad no tienen una relación directa entre catálogos. Ambas
se vinculan a una persona mediante `profesionales.profesion_id` y
`profesional_especialidades`. En el modelo vigente, el área base también usa
la segunda relación, aunque su papel es habilitar la asignación al consultorio.

## Problemas encontrados y correcciones

- La API ya aceptaba especialidades al crear al profesional, pero el formulario
  no las ofrecía. Ahora el mismo modal permite elegir profesión, área y
  especialidades, separa las opciones por tipo y permite escoger la principal.
  La ficha y los vínculos se crean con una sola petición y transacción.
- Los nombres de áreas de Consultorios priorizaban un diccionario fijo. Ahora
  priorizan el catálogo persistido para reflejar una edición de nombre.
- Se añadió Editar en los catálogos, usando el mismo modal. Solo modifica el
  nombre, verifica duplicados y deja auditoría. No cambia códigos ni identidades.
- La edición de una especialidad conserva su código. Se corrigió la generación
  de códigos para poder reutilizar un nombre antiguo después de renombrarlo,
  sin colisionar con la identidad anterior ni duplicar un nombre vigente.

## Límites que siguen presentes

- Las áreas y sus servicios permitidos están definidos en
  `app/domain/office.py`. Crear una especialidad con un nombre de área nueva no
  crea un área asistencial: la API la devuelve como `es_area=false` y rechaza
  usar su código como `area_codigo`. Es la segunda prueba de integración.
- No existe una relación de especialidades o áreas permitidas por profesión.
  El administrador puede asignarlas de forma independiente. El sistema verifica
  que existan y estén activas, pero no acredita compatibilidad profesional.
- Las nuevas especialidades no habilitan servicios clínicos automáticamente.
- La edición general de una ficha mantiene la acción separada Especialidades
  para modificar los vínculos de personas ya existentes.

Estos límites son del modelo, no errores de guardado. Para restringir el flujo
por profesión o admitir nuevas áreas operativas haría falta definir esas reglas
y hacer configurables las relaciones correspondientes; no se inventaron reglas
clínicas durante esta revisión.

## Evidencia

- `tests/integration/test_mysql_staff_flow.py`: dos pruebas con MySQL real y
  relaciones persistidas, aprobadas.
- `tests/unit/test_staff_catalog.py`: edición, identidad estable, auditoría,
  duplicados, permisos y protección de servicios heredados.
- 89 pruebas backend y 49 de interfaz aprobaron durante la revisión inicial.
- Revisión visual con datos sintéticos: se crearon profesión y especialidad,
  se editó la especialidad y se creó una ficha con profesión, área y especialidad
  principal desde el mismo modal. Capturas en `docs/audits/personal-flujo-vinculos-20261021.png`
  y `docs/audits/personal-profesional-vinculado-20261021.png`.
