# Revisión de admisión y FUA de gestantes

20 de octubre de 2026. Alcance: formulario de admisión, cálculo de edad gestacional,
copia de impresión, calibración y posibles ampliaciones. No es una auditoría
completa de seguridad, de todas las rutas ni una certificación de conformidad SIS.

## Cambios de esta revisión

- Retirado el mensaje «Registre la edad valorada o revise la fecha probable de
  parto para calcularla». Sin datos, el campo queda vacío y no se genera un párrafo
  de ayuda vacío. Se conserva la ayuda cuando existe una edad calculada o valorada.
- Desacoplada la comprobación de semanas del armado completo de valores de
  impresión: `gestationalWeeksForPrint` sirve tanto a pendientes como a impresión.
  Se mantienen las reglas de gestante, semanas enteras, dato cero y copia guardada.
- La E2E existente comprueba ahora también el estado vacío y la ausencia del mensaje
  en escritorio y móvil, antes de verificar FPP, valoración profesional y PDF.

## Qué conviene imprimir después

| Campo | Datos actuales | Trabajo necesario / prioridad |
| --- | --- | --- |
| Número de CPN | No hay captura estructurada en esta admisión. | Primera ampliación materna recomendada, junto con altura uterina. Capturar el número real del control del embarazo actual, validarlo y conservarlo con la atención. No contar automáticamente todas las consultas de la paciente. |
| Altura uterina | No hay captura estructurada. | Capturar la medición en cm. El instructivo SIS indica 0–45 cm y obligatoriedad desde semana 14. El cero medido debe distinguirse del dato ausente. No deducirla de la edad gestacional, talla o peso. |
| Diagnósticos, descripción, CIE-10 y tipo | El backend admite diagnósticos, los valida contra catálogo y los persiste; esta admisión no tiene selector y la copia FUA todavía no los proyecta. | Siguiente integración general útil: captura profesional, descripción y tipo documentados, copia inmutable y posiciones de impresión. No convertir el IMC o el estado gestante en un diagnóstico automático. |
| Código de prestación / adicionales | El backend admite prestaciones, pero el código es texto de catálogo y el modelo no declara una homologación SIS. | Verificar equivalencias y reglas SIS antes de imprimir. La modalidad «Ambulatoria» o el grupo «Gestantes» no determinan por sí solos una prestación. |
| Control puerperal | Hay fecha real de parto; falta número de control. | Agregar número 1/2 en la atención puerperal correspondiente. No calcularlo solo por días desde el parto. |
| Parto vertical | No se registra el acto del parto en esta admisión. | Agregar solo con el registro real de la atención del parto. No inferirlo del tipo de embarazo único/múltiple o de una preferencia. |
| Consejería nutricional | Hay indicadores y valoración nutricional. Eso no acredita una consejería realizada. | Requiere registrar expresamente la actividad y su procedimiento cuando corresponda. No marcarla por tener peso, talla o un resultado nutricional. |
| Hemoglobina | El modelo nutricional admite Hb y fecha, pero esta pantalla no captura el resultado. | El instructivo indica resultado del dosaje en el reverso, en g/dL. No copiarlo a «HB. GLICOSILADA» del anverso: es otro examen. Requiere integración con resultados/procedimientos. |

La opción de menor alcance para el bloque materno es agregar **CPN y altura uterina**,
con campos opcionales para compatibilidad y validación según la atención. Requiere
diseñar su almacenamiento clínico y proyección al FUA; no basta agregar texto a la
plantilla. Ninguna de estas ampliaciones se ha añadido automáticamente en esta revisión.

## Buenas prácticas comprobadas

- El servidor construye la copia FUA con datos clínicos y maestros de la atención.
  `FuaPrintInput` rechaza campos clínicos inventados por el cliente (`extra="forbid"`).
- El guardado de la atención, sus detalles y su copia se realiza en una transacción.
- Solo una atención guardada habilita la impresión; la copia conservada es la fuente
  del diálogo. Reimprimir no recalcula la edad ni altera la historia.
- La valoración profesional tiene prioridad sobre FPP; no se inventan días cuando
  solo se registraron semanas. Los valores inválidos o ausentes quedan pendientes.
- `GestationalAgeField` usa Composition API, modelo tipado y `computed` para el dato
  derivado. El control tiene etiqueta accesible y la actualización tiene `role=status`.
- Las posiciones del FUA son botones con etiqueta, teclado, foco visible y hover.
- La calibración permite solo geometría en almacenamiento del navegador, conserva
  posiciones existentes y exige revisar nuevas casillas antes de impresión física.
- La prueba de navegador usa una paciente ficticia y una base MySQL desechable;
  comprueba API, persistencia, documento descargado y conservación histórica.

## Hallazgos pendientes, por prioridad

1. **P2 — Proteger el borrador clínico al salir.**
   `frontend/src/views/AtencionNuevaView.vue:1121` y `:1135`: las guardas actuales
   contemplan cambios del editor del paciente y operaciones en curso, pero no
   modificaciones sin guardar de las medidas, FPP o edad gestacional. Navegar fuera
   antes de guardar puede perder esos datos. Conviene una protección común del
   borrador; no se incorporó un flujo nuevo de confirmación durante esta limpieza visual.
2. **P3 — Unificar fecha local y timestamps con zona en las previsualizaciones.**
   `frontend/src/utils/pregnancy.ts:19` y `frontend/src/utils/fuaDraft.ts:39` toman
   los primeros diez caracteres. `app/services/fua_print.py:55` convierte timestamps
   con zona a Lima. La UI actual envía fecha/hora local sin zona y la impresión final
   viene del servidor; si otra entrada pasa UTC a estos helpers, la sugerencia puede
   diferir un día cerca de medianoche. Normalizar antes de ampliar sus consumidores.
3. **P3 — Seguir reduciendo la vista de admisión por secciones.**
   `frontend/src/views/AtencionNuevaView.vue:582`: la vista conserva carga de catálogos,
   selección, captura, guardado y varias secciones visuales. El campo nuevo ya está
   separado; conviene extraer mediciones y estado de borrador en cambios propios,
   preservando sus contratos y pruebas, antes de sumar más campos maternos.

## Validación de esta revisión

**70 pruebas dirigidas aprobadas**, tipos, lint y compilación correctos; detector
de interfaz sin hallazgos para el componente modificado. **E2E aprobada** con
comprobación de persistencia MySQL. `gestante-fua.spec.ts` revisa estado vacío, escritorio/móvil,
FPP de 30 semanas y 2 días, prioridad de 29 semanas valoradas, PDF y reimpresión.
La evidencia de la nueva ejecución se conserva en `output/gestante-fua-revision-20261020/`.
La alineación con una impresora física sigue necesitando su prueba de papel habitual.

## Referencias

- [SIS: RJ 000178-2024-SIS/J y directiva 002-2024-SIS/GREP-V.02](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j).
- [Directiva y anexos: formulario y llenado materno, pp. 11, 29–30; dosaje de hemoglobina en el reverso](https://cdn.www.gob.pe/uploads/document/file/7310926/6245149-directiva-n-02-2024-sis-grep-v-02-actualizado.pdf).
- [SIS: criterios de registro modular por curso de vida de 2026](https://www.gob.pe/institucion/sis/normas-legales/7772769-000002-2026-sis-grep), relevantes antes de ampliar códigos de prestación.
- [Web Interface Guidelines: reglas de revisión](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), consultadas el 20/10/2026. Se aplicaron las reglas pertinentes de etiquetas, foco, actualizaciones, estados vacíos y diseño adaptable al flujo revisado.
