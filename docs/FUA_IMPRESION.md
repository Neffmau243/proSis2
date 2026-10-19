# Prellenado de la FUA en papel para uso local

## Alcance y referencia

Implementado como **prellenado parcial del anexo 1 (prestaciones de salud)**, no
como FUA digital, emisión oficial, acreditación en línea ni envío SETI-SIS.
El proyecto funciona localmente para un establecimiento. La impresión debe ser
legible para revisión administrativa, sin presentar abreviaturas locales como
equivalencias oficiales ni garantizar aceptación por el SIS.
Referencia revisada: [RJ 000178-2024-SIS/J](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j),
[Directiva 002-2024-SIS/GREP V.02 actualizada, anexos 1 y 3](https://cdn.www.gob.pe/uploads/document/file/7310926/6245149-directiva-n-02-2024-sis-grep-v-02-actualizado.pdf?v=1733872542).
Se verificaron el formulario (p. 11), las categorías (pp. 15–17), identificación y
afiliación (pp. 19–20), etnia (p. 23), fecha (p. 25) y mediciones (p. 29).

La conformidad integral requiere revisión de la IPRESS y los catálogos/normativa
aplicables a cada prestación. El módulo no certifica esa conformidad.

## Código SIS: papel, contrato y almacenamiento

Contrastado con la directiva anterior (pp. 19–20) y la
[trama de datos SIS publicada en 2025](https://www.gob.pe/institucion/sis/informes-publicaciones/7041412-trama-de-datos-del-fua),
trama Atención, campos 9–12 (p. 9 del PDF).

| Casilla | Contrato admitido en la ficha | Columna existente |
| --- | --- | --- |
| DIRESA / DISA | 3 caracteres alfanuméricos; obligatoriedad según contrato | `sis_diresa`, VARCHAR(3) |
| Tipo / formato | 1 o 2 caracteres alfanuméricos | `sis_tipo`, VARCHAR(2) |
| Número de afiliación | 8 o 9 dígitos; conserva ceros iniciales | `sis_numero`, VARCHAR(9) |
| Secuencia / RN | Hasta 2 dígitos, solo cuando corresponda | `sis_secuencia`, VARCHAR(2) |

El ejemplo de tres casillas `040 | 2 | 00000001` es **ilustrativo**, no un
valor predeterminado. Para el papel, la directiva describe 3 dígitos de DIRESA y
un dígito/letra de tipo; el contrato electrónico permite las longitudes más
amplias de la tabla. `2` identifica el régimen subsidiado con DNI; no distingue
por sí solo SIS Gratuito de SIS Para Todos ni acredita que la cobertura esté activa.
Para esos planes subsidiados, el número puede corresponder al DNI/CE según la
directiva, pero debe provenir de la acreditación, no inferirse automáticamente.

Los valores se guardan como texto; no se convierten a números. Frontend y
backend validan longitud y caracteres. El backend valida el resultado completo
del PATCH bajo bloqueo de fila: si hay algún dato SIS, tipo y número deben estar
presentes. Se admite la afiliación íntegramente vacía para carga pendiente.
Las cuatro columnas ya estaban disponibles en la migración `20260919_0015_patient_sis`;
este ajuste visual no requiere otra migración ni inventa datos para pacientes.

## Flujo

1. En **Datos del paciente**, debajo de **Seguro**, revise o complete las tres
   casillas de afiliación SIS, la **Secuencia/RN** y la **Etnia declarada**.
   La secuencia no es el régimen del seguro y se guarda tal cual; la etnia se
   elige del catálogo de etnias del backend. Un paciente con etnia o secuencia
   pendientes puede completarlas aquí sin registrar uno nuevo.
   **Guardar cambios** actualiza la ficha del paciente por PATCH, incluyendo
   solo campos modificados. Los cambios pendientes deben guardarse antes de la
   atención.
2. Pulse **Guardar atención**. Se muestra la confirmación sin navegar ni borrar
   los datos; la atención queda en modo lectura para evitar un segundo registro.
3. **Imprimir S.I.S.** se habilita con la copia devuelta por el servidor. El resumen
   muestra en **Personal que atiende** el nombre del profesional guardado en la
   atención. **Tipo de personal en la FUA** muestra la categoría de la sede
   (por ejemplo, **De la IPRESS**); el lugar también sale de la sede y el tipo de
   atención sale de la modalidad guardada. No hay un
   segundo formulario para definir SIS, etnia, personal o lugar al imprimir.
4. Revise los pendientes y calibre la hoja en la vista previa conservada.
   **Imprimir sobre FUA preimpresa** abre el diálogo del navegador; también puede elegir
   «Guardar como PDF». Para revisar los datos sobre el formulario use
   **Ver FUA / guardar PDF** y elija «Guardar como PDF»: incluye la imagen
   y una leyenda de revisión/prellenado parcial. El RENIPRESS preimpreso no se
   sobreimprime en el modo solo datos; se muestra en la copia de revisión.
5. Si falta la afiliación, las casillas quedan vacías. El ETL o la captura
administrativa deben traer valores reales; no se asignan códigos por defecto
ni se copia automáticamente el DNI. No se consultó ni modificó la afiliación
de pacientes reales durante las pruebas de esta interfaz.

### Código del tipo de seguro de ETLSIS

La tabla histórica `EESS_SIS` está mal nombrada: es el catálogo de seguros y
no una relación de establecimientos. Sus códigos se conservaron en
`seguros.codigo_sis`: `001` Sin seguro, `002` SIS Gratuito, `003` SIS
Afiliación Temporal, `004` SIS Semi Subsidiado, `005` SIS NRUS, `006` SIS Para
Todos, `007` EsSalud, `008` Sanidad y `009` Particular. El catálogo genérico
`SIS` y `OTRO` no reciben un código artificial porque no identifican un plan
de origen. Este código de catálogo **no es** la casilla `sis_tipo` del
asegurado: esta última proviene de la afiliación/acreditación individual y no
se deduce del nombre de su seguro.

La revisión de fuentes oficiales y la diferencia con el catálogo de financiadores
HIS están documentadas en [SEGUROS_PERU.md](SEGUROS_PERU.md). El editor y el
backend conservan el tipo/formato y la DISA del contrato ingresado, sin deducirlos
del plan ETLSIS ni de la sede de registro.

6. La reimpresión desde el detalle reutiliza la copia guardada; no hace otro POST
   de atención ni emite otro número.

Guardar normalmente también conserva la copia, aunque los complementos no
declarados quedarán vacíos. La copia guardada es de solo lectura: no se ofrece
edición posterior de información clínica/documental en este módulo. Las
atenciones anteriores a la migración no se rellenan retrospectivamente ni pueden
reimprimirse con este flujo; requieren un procedimiento explícito de revisión.

## Correspondencia del backend

| Campo | Origen y tratamiento |
| --- | --- |
| Personal y lugar de atención | Configuración del establecimiento guardada en backend; valores iniciales IPRESS e INTRAMURAL. AISPED requiere código. No se eligen al imprimir. |
| Atención | Modalidad de la atención guardada. No se cambia desde la impresión. Es distinto del módulo de referencias de salida. |
| Identificación | Documento del paciente. DNI → TDI 2, CE → TDI 3. Para uso local, PAS, DE y OTRO imprimen su abreviatura y número, con una leyenda que explica el nombre del documento y aclara que no es código TDI SIS. El TDI del snapshot sigue nulo; no se modifican los registros históricos. Una identidad vacía, desconocida o inconsistente sigue bloqueando la impresión. |
| Código del asegurado | `pacientes.sis_diresa`, `sis_tipo`, `sis_numero` y `sis_secuencia`; copia por atención solo cuando el seguro de la ficha pertenece al régimen SIS. Cambiar a otro régimen o quitar el seguro limpia la afiliación actual, sin modificar copias históricas. No se infiere afiliación del DNI. Secuencia no equivale a régimen. |
| Apellidos, nombres y nacimiento | Datos del paciente al registrar la atención, incluidos otros nombres. Un apellido ausente queda vacío. |
| Historia clínica | `historia_clinica_snapshot`, no la historia actual después de una modificación. |
| Etnia | Código declarado del paciente, validado contra el catálogo activo de etnias del backend. No se infiere por nombre, aspecto o domicilio. |
| Fecha y hora | `fecha_atencion`; si trae zona horaria, la copia usa America/Lima. No usa fecha de impresión ni la hora de fin. |
| Peso, talla, PA, IMC, PAB | Valores de la atención; IMC calculado por el backend. Unidades kg, cm y mmHg. No imprime PA parcial. El PAB solo se captura en el grupo general; gestantes y puérperas usan ese espacio del formato para la fecha de parto. |
| IPRESS | Nombre del catálogo. Un RENAES numérico de hasta ocho dígitos se normaliza con ceros a la izquierda para la casilla RENIPRESS; nunca se usa el ID interno. No se sobreimprime cuando la sede declara papel preimpreso. |
| Responsable | Nombre, documento y colegiatura del profesional verificado por el servicio. No imprime firmas ni sellos. |
| Salud materna y parto | Marcas según el grupo declarado. El recuadro de parto imprime la FPP de la gestante (`fecha_probable_parto`) o la fecha real del parto de la puérpera (`fecha_parto`, migración `20261007_0028_delivery_date`); en el grupo general queda vacío. |

El contrato agrega `fua_datos` a `AttentionCreate` y `fua_impresion` a
`AttentionResponse`. `fua_impresion` es JSON versionado, creado **por el servidor**
en la misma transacción que la atención, con el paciente bloqueado por el flujo
existente. No se acepta un IMC/documento/nombre proporcionado como complemento.
La migración `20260919_0014_fua_print` agrega una columna nullable; no borra ni
modifica las atenciones previas. Se aplicó a la base local durante la implementación.

### Revisión de campos y bloqueo de impresión (12/10/2026)

El instructivo de la Directiva 002-2024-SIS/GREP-V.02, pp. 15–17, define
**De la IPRESS** como personal con vínculo contractual con la IPRESS e
**Intramural** como atención dentro de ella. Son categorías válidas, pero la
aplicación las copia de la configuración de la sede; no verifica automáticamente
el vínculo contractual ni la ubicación física de cada atención. El nombre del
profesional corresponde al responsable conservado en la atención, no a esa
categoría. El resumen ahora distingue ambos conceptos y muestra la IPRESS y su
RENIPRESS guardado incluso cuando el código está configurado para no imprimirse.

Una historia clínica de 19 caracteres podía superar el ancho del perfil inicial
a 8 pt y bloquear la impresión pese a tener posiciones calibradas. El texto
continuo ahora reduce su fuente dentro de la casilla, hasta 5 pt, usando el mismo
resultado en vista previa e impresión. No se cambian coordenadas, ancho, paso ni
contenido guardados. Los caracteres con paso fijo mantienen su separación; el
texto que tampoco cabe al tamaño mínimo sigue exigiendo ajustar la casilla.

La impresión sobre papel preimpreso sigue requiriendo una prueba física. El
diálogo muestra el motivo del bloqueo y ofrece acceso directo a calibración.
La opción A4 cambia únicamente el tamaño del perfil y lo deja pendiente de
calibrar: debe usarse solo cuando la hoja física mida 210 × 297 mm, no por el
tamaño de la página del PDF que contiene el anexo.

## Límites detectados

- La afiliación y etnia se conservan **en el paciente** y se copian por atención.
  No son resultado de una acreditación automática con el SIS. El catálogo local
  identifica el seguro genérico `SIS`, no discrimina todos sus planes comerciales.
- La modalidad clínica existente admite ambulatoria/emergencia; la categoría
  REFERENCIA se declara en el complemento documental. No se amplió el catálogo
  clínico ni se equiparó una referencia de ingreso a una referencia de salida.
- Mediciones obligatorias según el caso pueden estar vacías en el sistema. Se
  advierte antes de imprimir y exige confirmar que se completarán manualmente
  las que correspondan; no se promete una FUA completa.
- El PAB solo se captura en el grupo general: la admisión lo cede a la fecha de
  parto en gestantes y puérperas. Por eso los avisos previos a la impresión ya no
  piden PAB en esos grupos y, en su lugar, piden la fecha del recuadro de parto
  (FPP en gestantes, fecha real en puérperas). Si la IPRESS necesita PAB también
  en salud materna, requiere revisar el flujo asistencial y volver a añadirlo.
- No se imprimen aún prestaciones, diagnósticos, vacunas, hospitalización,
  destinos, firmas/sellos, datos de recién nacidos ni todos los campos preventivos.
- El antiguo bloque de configuración `040 | 16 | 2 | 00001` procede de la
  aplicación histórica de 2016 y no coincide con la estructura vigente del
  número de FUA. El sistema lo conserva solo como evidencia en el archivo ETL;
  no se usa para emitir ni imprimir.
- Al registrar un FUA, la aplicación usa `RENIPRESS(8) | lote(2) |
  correlativo(8)`: por ejemplo, la fuente `0001291` se normaliza a `00001291`
  y para 2026 el resultado inicial es `00001291-26-00000001`. El RENIPRESS se
  toma del catálogo de la IPRESS; nunca del ID interno ni de campos editables
  por el usuario. La secuencia es atómica por sede y año de emisión.
- Este formato no sustituye la asignación de rango que debe confirmar la
  DIRESA/GERESA, la Red o la UDR. Antes de usarlo como FUA oficial, la IPRESS
  debe verificar el RENIPRESS activo y que el correlativo local no se cruce con
  sus formatos preimpresos o con otro sistema. No existe aún integración SETI.

## Calibración y privacidad

Desde el 19/10/2026, la afiliación se imprime en tres casillas independientes:
**DIRESA | tipo/formato | número**, sin unir el tipo al número con un guion.
El sufijo opcional Secuencia/RN se conserva junto al número cuando existe
(en copias versión 1 se conserva el componente histórico).
Vista previa, PDF y papel usan las mismas tres posiciones, ajustables por separado.
Los perfiles anteriores con `sis_numero_completo` se migran añadiendo las casillas
de tipo y número según el formulario, tomando la DIRESA guardada como referencia
de alineación; conservan los demás campos y desplazamientos.
La migración exige comprobar la alineación una vez antes de imprimir en papel;
después de confirmarla, no vuelve a invalidarla al abrir el diálogo.

El perfil inicial es **216 × 356 mm** y las coordenadas parten de una cuadrícula
del anexo 1 oficial V.02, usado en 2025. La medida inicial no certifica el tamaño
de la hoja física disponible en la IPRESS. Ajuste ancho, alto, desplazamientos y
cada campo (X/Y/ancho/alto/fuente/paso por carácter). El omitir caracteres
iniciales permite no repetir un prefijo de año ya impreso. Los campos pueden
desactivarse, excepto la identificación y su leyenda cuando contienen datos;
no se permite omitir caracteres de esos campos.

La leyenda de uso local tiene su propio campo ajustable. Las calibraciones
anteriores conservan sus coordenadas y añaden este campo, pero requieren revisar
y confirmar otra vez la alineación. Números largos no se recortan: amplíe el campo
o ajuste su fuente dentro de los límites antes de imprimir.

Pruebe cruces sin datos en papel blanco y superponga la hoja. Solo confirme la
calibración después de comprobarla físicamente. Un cambio de geometría invalida
esa confirmación. Texto que no cabe o sale de la hoja bloquea la impresión;
no se corta silenciosamente. Cambiar de impresora/papel exige volver a comprobar.

En el diálogo de impresión: escala 100 %, sin encabezados/pies, márgenes cero y
tamaño idéntico en el controlador. El navegador no puede validar alimentación,
área no imprimible, orientación física ni escala impuesta por la impresora.

Desde el 14/10/2026, **todos** los perfiles usan exclusivamente
`frontend/src/assets/fua-v02-referencia.png`, extraído del formulario de la página
11 de la directiva oficial. Es la misma imagen en Vista previa y calibración y en
Ver FUA / guardar PDF. No hay selector de plantilla ni escaneo alternativo.
La antigua imagen se archivó en `docs/referencias/fua/fua-historica.webp` y ya no
se importa ni se incluye en el build. Las posiciones iniciales corresponden al
anexo oficial; las calibraciones guardadas mantienen todas sus coordenadas.

Un perfil antiguo (`historica` o sin identificador de plantilla) se normaliza a
`sis-v02` automáticamente y queda pendiente de comprobar la alineación una vez,
pues su confirmación anterior correspondía a otra imagen. La versión normalizada
se guarda en el mismo navegador. Confirmar la prueba física persiste el estado y
las siguientes aperturas ya no repiten esa migración ni esa comprobación.

La calibración se guarda automáticamente en `localStorage`, clave
`ipress.fua-layout.v1`: es **por navegador y origen de la aplicación**, compartida
por todas las cuentas y pacientes. No está en MySQL ni en la cuenta. Cambiar de
paciente, cerrar sesión o elegir otro campo para ajustar no invalida la confirmación.
Cambiar geometría sí la invalida y conserva los nuevos valores como pendientes.
`localhost`, `127.0.0.1`, otro puerto y otro equipo tienen almacenamientos distintos;
limpiar datos del navegador también elimina el perfil. El diálogo lo explica y
permite exportar/importar JSON sin información clínica. Importar conserva posiciones
y exige confirmar la impresora de destino una vez. Los errores de lectura/escritura
son visibles y no se sobrescribe automáticamente un perfil ilegible al abrir.

La referencia oficial queda fuera de **Imprimir sobre FUA preimpresa**
y de **Imprimir prueba sin datos**. La copia con referencia se puede revisar sin
haber confirmado la prueba física, pero conserva los controles de identidad,
desbordamiento y reconocimiento de faltantes. El navegador espera que la imagen
cargue antes de abrir la impresión. Solo la geometría pasa al almacenamiento o a
su exportación; nunca nombres, documentos, afiliaciones ni mediciones.

**Ver FUA / guardar PDF** es el botón principal del diálogo y abre la vista del
navegador con formulario y datos. Allí se elige Guardar como PDF; se sugiere el
nombre `atencion-NOMBRES APELLIDOS-AAAA-MM-DD.pdf`, con los datos y la fecha de
atención de la copia guardada (no la fecha de descarga),
conservando tildes y omitiendo caracteres no válidos para nombres de archivo.
El título de la pestaña se mantiene con ese nombre mientras está abierto el
diálogo de impresión y se restaura al cerrarlo, para evitar que Chromium use
el título de Admisión como nombre del PDF.
La prueba sin datos conserva un título genérico. La imagen del
formulario se imprime como elemento de la página, por lo que aparece incluso con
Gráficos de fondo desactivado. **Imprimir sobre FUA preimpresa** es la opción
secundaria para una hoja física que ya contiene el formato; su vista sin imagen
es intencional.

## Comprobación

Pruebas unitarias de backend: validación de grupos, campos no admitidos, ceros
iniciales, equivalencias TDI, copia inmutable y datos no inventados.
Frontend: marcas, fechas, PA incompleta, escape HTML, almacenamiento permitido,
límites de texto/hoja y prueba sin datos. Type-check, lint y build de producción.
Prueba visual con un fixture sintético independiente: `/tests/fua-print-harness.html`
y `/tests/fua-print-mobile.html` solo en Vite de desarrollo, fuera del build.
El fixture no usa autenticación, APIs ni historias reales.

Pendientes para la puesta en uso: hoja física/escaneo y medida exacta, impresora,
validación de códigos y protocolo por la IPRESS, ensayo físico de impresión.
No se realizó una impresión física ni se crearon atenciones reales para probar.

## Verificación de las casillas SIS (20/09/2026)

El componente `PatientSisCodeFields` agrupa el código bajo Seguro en Datos del
paciente y conserva el editor y sus permisos. La ficha muestra únicamente las
tres casillas; el control de secuencia y la nota se retiraron después de la
primera revisión visual, por solicitud del usuario. La impresión sigue tomando la copia
generada por el servidor, nunca un formulario alternativo de afiliación.
Pruebas frontend: 29; pruebas backend focalizadas SIS/paciente/impresión: 48.
Type-check, lint y build correctos (aviso de tamaño del bundle general existente).
Fixture visual interactivo: `/tests/patient-sis-code-harness.html`, solo desarrollo,
sin API ni persistencia de datos. Verificados en escritorio y a 320 px: entrada
en tres casillas, errores, conservación de ceros, secuencia opcional y bloqueo
de edición. La ruta real de Admisión solicitó iniciar sesión; no se probó un
guardado autenticado ni se modificaron pacientes reales. No se acredita cobertura
SIS en línea.

## Registro de la revisión previa (19/09/2026)

La ampliación conserva los componentes y estilos existentes de Element Plus.
La revisión original incluía complementos editables; el flujo actual los toma de
paciente/sede/atención y muestra un resumen de solo lectura junto a la vista previa.
La vista previa mantiene la geometría en milímetros; el escaneo de apoyo queda
local y fuera de la impresión. La configuración personal conserva solo geometría,
sin datos identificativos ni clínicos del paciente.

Al cierre pasaron 129 pruebas de backend y 21 de frontend, además de type-check,
lint y build. El detector Impeccable no reportó hallazgos (`[]`). La revisión
externa cerró las incidencias de arrastre de afiliación y espacios, tras comprobar
la sincronización del borrador y las pruebas de escritura carácter a carácter.
Las capturas de escritorio y móvil corresponden a la revisión visual previa,
con datos sintéticos: `frontend/tests/fua-desktop.png` y
`frontend/tests/fua-mobile.png`. No hubo recaptura final por un fallo de conexión
del navegador. No se ensayó impresión física ni se crearon atenciones reales.
