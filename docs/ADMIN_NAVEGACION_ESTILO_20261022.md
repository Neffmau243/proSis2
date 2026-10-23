# Navegación y estilo de administración

## Alcance

Se unificaron establecimientos, detalle de establecimiento, áreas, consultorios,
detalle de consultorio, catálogo de servicios y Personal y cuentas.

- `AdminPageLayout` aporta la ruta y una única superficie de trabajo, sin tarjetas anidadas.
- `AdminPageHeader` comparte tipografía, descripción, espaciado y ubicación de acciones.
- Los colores y tamaños de controles se limitan a estas superficies administrativas.
- Se retiró el menú superior repetido. El menú lateral conserva los accesos generales.
- Las rutas internas muestran nombres del establecimiento, área y consultorio cargados.
  Funcionan también al abrir directamente la URL del consultorio.
- Los enlaces de la ruta y el botón de regreso conservan sede y área. El regreso utiliza
  los datos actuales del consultorio y descarta filtros de área obsoletos.
- Al limpiar filtros del directorio, la ruta elimina también ese contexto.

Ejemplo de ubicación:

`Administración > Establecimientos > C.S. ALTO SELVA ALEGRE > Área: NUTRICION > Consultorios > NUTRICION`

El área identifica el contexto; no enlaza a una supuesta ficha de área por sede,
porque el catálogo actual de áreas es compartido.

### Presentación horizontal

La ruta se presenta en horizontal con separadores entre niveles. La ubicación actual
se resalta; los enlaces y sus filtros se conservan. En móvil se mantienen controles
de 44 px y los niveles pueden continuar en la siguiente línea para que los nombres
se lean completos. Esta presentación sustituye la escalera vertical.

Comprobación de la presentación horizontal: tipos, compilación y ESLint correctos.
Revisión visual en escritorio y móvil sin desbordamiento horizontal. Se conservan
los enlaces y filtros previamente cubiertos por las pruebas administrativas.

- [Ruta horizontal en escritorio](audits/admin-ruta-horizontal-escritorio-20261022.png)
- [Ruta horizontal en móvil](audits/admin-ruta-horizontal-movil-20261022.png)

## Límite de esta entrega

Solo se modificó presentación y navegación administrativa. Esta entrega no modifica
API, permisos, modelos, base de datos, registro de admisión, asignaciones clínicas ni
generación de FUA. Se conservaron los cambios anteriores del espacio de trabajo.

## Verificación

- 112 pruebas aprobadas de administración y regresiones de admisión/FUA con dos trabajadores.
  Se añadieron casos de URL directa, regreso filtrado, limpieza de contexto y filtros obsoletos.
- Comprobación de tipos, compilación de producción y ESLint de los archivos afectados.
- Detector de distribución visual sin hallazgos.
- Revisión visual en escritorio (1280 × 720) y móvil (390 × 844), sin desbordamiento
  horizontal de página en las superficies comprobadas. Controles de móvil con altura mínima de 44 px.
- La inspección local fue de lectura y navegación; no se crearon ni editaron registros reales.

Evidencias:

- [Consultorio en escritorio](audits/admin-ruta-unificada-consultorio-escritorio-20261022.png)
- [Consultorio en móvil](audits/admin-ruta-unificada-consultorio-movil-20261022.png)
- [Establecimientos en escritorio](audits/admin-estilo-unificado-establecimientos-escritorio-20261022.png)
- [Establecimientos en móvil](audits/admin-estilo-unificado-establecimientos-movil-20261022.png)
- [Servicios en escritorio](audits/admin-estilo-unificado-servicios-escritorio-20261022.png)
- [Servicios en móvil](audits/admin-estilo-unificado-servicios-movil-20261022.png)
- [Áreas en móvil](audits/admin-estilo-unificado-areas-movil-20261022.png)
