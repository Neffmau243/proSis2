# Ubicación de los catálogos de personal

Se retiró la subvista «Áreas y especialidades» de Personal para evitar confundir la administración del catálogo con la asignación de una persona a un consultorio.

- **Personal → Profesiones:** crear, editar y eliminar profesiones.
- **Personal → Profesionales:** seleccionar la profesión y asignar las áreas y especialidades de cada persona.
- **Consultorios → Áreas y especialidades:** crear, editar y eliminar las opciones compartidas con las fichas de profesionales.
- **Consultorios → Consultorios:** configurar cada consultorio y sus asignaciones de profesionales.

Se reutiliza el mismo formulario, catálogo y API. No se eliminan registros ni se modifican relaciones existentes. Los selectores de Consultorios se actualizan después de guardar o eliminar una opción. La administración de áreas y especialidades conserva el permiso `PROFESIONAL_GESTIONAR`; el acceso a Consultorios conserva `CONSULTORIO_GESTIONAR`.

Esta ubicación sustituye las indicaciones anteriores que situaban la administración de áreas y especialidades en Personal.

## Verificación

- 34 pruebas de catálogos, Personal y Consultorios aprobadas.
- Compilación TypeScript, ESLint, detector de interfaz y build de producción aprobados.
- Verificación en localhost como administrador: Personal muestra únicamente Profesiones como catálogo; Consultorios muestra el catálogo de Áreas y especialidades y permite abrir/cancelar su formulario. No se modificaron registros reales.
- Evidencias: `docs/audits/personal-solo-profesiones-20261021.png` y `docs/audits/catalogos-en-consultorios-20261021.png`.
