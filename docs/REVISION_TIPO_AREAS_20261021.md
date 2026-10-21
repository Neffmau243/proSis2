# Tipo Área / Especialidad

La clasificación previa se calculaba solo por pertenencia a ocho códigos fijos.
Las altas y las ediciones no guardaban ningún tipo. Por eso toda alta nueva se
mostraba como Especialidad y no podía convertirse en Área.

Se agregó `especialidades.es_area` y se migraron las ocho áreas base. El formulario
ofrece Tipo de registro al crear y editar; el catálogo devuelve ese valor persistido.
El código del registro se conserva al cambiar el tipo. Los registros existentes no
se reclasifican automáticamente por su nombre.

Consultorios valida ahora las áreas personalizadas persistidas. El área nueva
dispone de su propio registro como servicio inicial y conserva el flujo normal de
asignación profesional y admisión. Las áreas base conservan sus servicios existentes.

Las áreas base no pueden cambiar de tipo ni eliminarse. Un registro personalizado
usado por consultorios o atenciones rechaza el cambio de tipo con 409. Los cambios
de nombre y las clasificaciones se auditan y se revierten juntos ante un error.

## Verificación

- 100 pruebas backend: catálogos, cambios de tipo, protección de usos, oficinas,
  contrato de migraciones y límites de configuración.
- 42 pruebas de interfaz: crear un área, recuperar su selección al editar,
  convertirla a especialidad sin duplicarla, proteger áreas base y regresiones
  de Personal, profesionales y consultorios.
- 3 pruebas MySQL con migraciones reales: incluye área personalizada, cambio de
  tipo en ambos sentidos, consultorio, asignación, paciente y admisión; el cambio
  posterior de un área en uso se rechaza.
- TypeScript, ESLint, Ruff y compilación Vite.
- En localhost se creó `ÁREA PRUEBA TIPO 2110` como Área, se recargó, se editó a
  Especialidad y se volvió a Área. Se comprobó su aparición en Área asistencial
  de Consultorios. El registro descartable se eliminó al terminar.

Evidencia: `docs/audits/personal-editar-tipo-area-20261021.png` y
`docs/audits/personal-area-nueva-consultorios-20261021.png`.
