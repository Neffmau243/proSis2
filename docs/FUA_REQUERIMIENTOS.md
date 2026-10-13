# Requerimientos para registrar e imprimir el FUA en una posta de salud

Fecha de investigación: 12 de octubre de 2026.

## Alcance

Lista para un sistema de establecimientos del primer nivel de atención en Perú que registra prestaciones y prepara el Formato Único de Atención del Seguro Integral de Salud (SIS). Se toma como formulario de salud el **anexo 1 de la Directiva 002-2024-SIS/GREP-V.02**. El anexo 2 corresponde a prestaciones administrativas y necesita un flujo distinto si el establecimiento lo utiliza.

El FUA es un instrumento del SIS, organismo adscrito al MINSA; no toda atención de una posta ni todo paciente implica una prestación financiada por SIS. Los datos de otra IAFAS deben tratarse con las reglas del formulario y del convenio aplicable.

La revisión encontró la V.02 aprobada por la RJ 000178-2024-SIS/J y la actualización para registro modular por curso de vida de 2026, que expresamente mantiene el diseño y los campos del FUA. No se identificó una resolución posterior que sustituya ese diseño en las fuentes consultadas. La búsqueda no constituye un inventario exhaustivo de toda modificación normativa.

Los requisitos de los apartados de datos derivan del formulario y su instructivo. Los requisitos de software e impresión se identifican como recomendaciones de implementación, para distinguirlos de las exigencias expresas del SIS.

## Fuentes oficiales

- **S1.** [RJ 000178-2024-SIS/J](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j), publicada el 30/11/2024. Aprueba la V.02 y deja sin efecto la V.01 de 2024.
- **S2.** [Directiva 002-2024-SIS/GREP-V.02 y anexos, PDF oficial](https://cdn.www.gob.pe/uploads/document/file/7310926/6245149-directiva-n-02-2024-sis-grep-v-02-actualizado.pdf?v=1733872542). Lectura del texto y revisión visual del formulario: pp. 11-12; criterios generales: pp. 6-8; instructivo de salud: pp. 14-39. Las páginas corresponden al PDF de 50 páginas.
- **S3.** [RG 000002-2026-SIS/GREP](https://www.gob.pe/institucion/sis/normas-legales/7772769-000002-2026-sis-grep), de 23/02/2026, vigente desde 01/03/2026, y [criterios técnicos RM-CV, PDF oficial](https://cdn.www.gob.pe/uploads/document/file/9494985/7772769-criterios-tecnicos-para-el-registro-modular-por-curso-de-vida-rm-cv-en-el-formato-unico-de-atencion-fua.pdf?v=1771946876). Revisados alcance y códigos, pp. 5 y 11-17; el numeral 6.4.1 mantiene el diseño del FUA.
- **S4.** [RG 000003-2026-SIS/GREP](https://www.gob.pe/institucion/sis/normas-legales/7861792-000003-2026-sis-grep), de 13/03/2026. Aprueba actualización de reglas de auditoría automatizada; la resolución remite al [Mirador GREP](https://www.sis.gob.pe/ipresspublicas/miradorgrep.html). Se verificó la resolución publicada; esta investigación no transcribe ni implementa todas las fichas del compendio.
- **S5.** [Conect@SIS / SETI-SIS](https://www.gob.pe/89767-plataforma-conect-sis-seti-sis). Referencia para una futura integración de validación y envío de FUA digital.

## Convenciones

- **General:** componente del registro ordinario de una prestación de salud; la validación debe considerar sus reglas y excepciones oficiales.
- **Condicional:** se completa al darse el supuesto indicado. Mantener la casilla disponible en la plantilla aunque no se utilice en una atención.
- **Digital:** requisito específico del FUA digital; imprimir desde un sistema informático no equivale por sí solo a implementar el FUA digital.

No debe interpretarse esta lista como que todas las casillas llevan un valor en cada consulta. Tampoco se deben sustituir datos desconocidos por valores inventados.

## Datos del anverso

| ID | Requerimiento | Aplicación | Referencia |
| --- | --- | --- | --- |
| RF-01 | Conservar el número de FUA con estructura `RENIPRESS de 8 dígitos / lote de 2 dígitos / correlativo de 8 dígitos`; el mismo número debe figurar en anverso y reverso. | General. La autoridad competente asigna el rango; no basta un correlativo local. | S2, pp. 14-15 |
| RF-02 | Registrar nombre y código RENIPRESS del establecimiento que brinda la atención. | General | S2, p. 15 |
| RF-03 | Registrar la categoría de personal que atiende: de la IPRESS, itinerante u oferta flexible; conservar la casilla y código AISPED cuando corresponda. | General; código AISPED condicional | S2, pp. 15-16 |
| RF-04 | Registrar lugar intramural o extramural y modalidad ambulatoria, referencia o emergencia conforme a la atención efectivamente brindada. | General | S2, pp. 16-18 |
| RF-05 | Para un paciente referido, imprimir código RENIPRESS y nombre de la IPRESS de origen, y número de hoja de referencia. | Condicional: referencia de ingreso | S2, pp. 17-18 |
| RF-06 | Registrar tipo y número de documento del paciente. El instructivo de esta versión identifica TDI 2 para DNI y TDI 3 para carné de extranjería. | General; otros supuestos de identidad requieren la regla aplicable, sin inventar equivalencias. | S2, pp. 18-19 |
| RF-07 | Imprimir el código de asegurado SIS: DIRESA/GERESA o equivalente, tipo de plan y número de afiliación; considerar el cuarto componente para recién nacidos cuando corresponda. | Asegurado SIS | S2, pp. 19-20 |
| RF-08 | Registrar institución y código de seguro de otra IAFAS en el bloque correspondiente. La leyenda usa 1 EsSalud, 2 FFAA, 3 SALUDPOL, 4 otros y 5 sin seguro. | Condicional; no confundir esta leyenda con otros catálogos del sistema. | S2, p. 20 |
| RF-09 | Imprimir apellido paterno, apellido materno, primer nombre y otros nombres en sus casillas; si existe un solo apellido, dejar vacío el otro. | General | S2, pp. 20-21 |
| RF-10 | Registrar sexo, fecha de nacimiento y número o denominación alfanumérica de historia clínica. Fechas separadas en día, mes y año. | General | S2, pp. 21-23 |
| RF-11 | Registrar código de etnia cuando sea pertinente, usando la normativa y el catálogo aplicables. | Condicional; no inferir por nombre o domicilio. | S2, p. 23 |
| RF-12 | Marcar gestante o puérpera; consignar fecha probable de parto o fecha real de parto según el caso. | Condicional. La fecha real es obligatoria en las prestaciones de parto y puerperio indicadas por el instructivo; revisar también código 306 y RC30. | S2, pp. 21-23; S3, p. 16 |
| RF-13 | Registrar DNI, CNV o afiliación del recién nacido en las casillas RN1, RN2 y RN3 según orden de nacimiento, con las excepciones previstas para óbito o natimuerto. | Condicional: atención de parto; aplicar asimismo reglas actualizadas RM-CV. | S2, pp. 23-25; S3, p. 16 |
| RF-14 | Registrar fecha y hora de atención, código UPS y código de prestación. | General. En hospitalización la fecha responde a alta o corte administrativo según instructivo. | S2, pp. 11 y 25-27 |
| RF-15 | Permitir prestaciones preventivas adicionales efectivamente brindadas el mismo día bajo las condiciones del instructivo; admitir los códigos modulares 301-306 conforme a RM-CV. | Condicional; evitar crear un FUA por cada actividad de una atención integral que pueda consolidarse. | S2, pp. 8 y 26-27; S3, pp. 11-17 |
| RF-16 | Registrar ingreso, alta y corte administrativo; conservar código de autorización y FUA vinculado cuando sean aplicables. | Condicional: hospitalización, corte u otros supuestos de vinculación. Incluye apoyo diagnóstico 071 según origen previsto. | S2, pp. 14-15 y 27-29 |
| RF-17 | Mantener concepto prestacional y bloque de sepelio del formulario; no reutilizar una consulta ordinaria como FUA de sepelio. | Condicional; sepelio requiere FUA exclusivo y su normativa específica. | S2, pp. 11 y 29 |
| RF-18 | Registrar destino del asegurado: alta, cita, hospitalización, emergencia, referencia, contrarreferencia, fallecido o corte administrativo según las opciones de la plantilla; para referencia/contrarreferencia de salida, registrar IPRESS destino y número de hoja. | Según prestación y reglas vigentes. Es distinto de la referencia de ingreso RF-05. | S2, p. 11; S3, p. 15, RC04 |
| RF-19 | Registrar peso en kg, talla en cm, presión arterial en mmHg y perímetro abdominal en cm; mantener casilla IMC en kg/m². | El instructivo declara obligatorios peso, talla, PA y PAB en prestaciones preventivas y recuperativas. Resolver aplicabilidad/excepciones con las reglas clínicas vigentes, sin dispensarlas automáticamente por configuración local. | S2, pp. 11 y 29; S3, p. 15, RC14 |
| RF-20 | Registrar control prenatal, edad gestacional, altura uterina, parto vertical y control puerperal según la atención. | Condicional: salud materna. El instructivo señala obligatoriedad de altura uterina a partir de semana 14 y exige fecha de parto en control puerperal. | S2, pp. 29-30 |
| RF-21 | Registrar edad gestacional del RN, APGAR al minuto y a los cinco minutos y corte tardío de cordón cuando corresponda. | Condicional: atención del recién nacido | S2, p. 30 |
| RF-22 | Registrar número de control CRED, prematuridad, bajo peso al nacer, enfermedad congénita/secuela y evaluación TAP/EEDP/TEPSI efectivamente realizada. | Condicional: atención infantil | S2, pp. 31-32 |
| RF-23 | Registrar evaluación integral, consejería nutricional/integral, VACAM y tamizaje de salud mental normal o patológico según intervención y curso de vida. Si el tamizaje es patológico, incluir diagnóstico CIE correspondiente. | Condicional | S2, pp. 31-34; S3, p. 16, RC34 |
| RF-24 | Registrar valores de tamizaje de patologías crónicas: hemoglobina glicosilada, albúmina en orina y depuración de creatinina según diagnóstico y prestación. | Condicional. Verificar unidades del catálogo/procedimiento antes de implementar: la etiqueta de Hb glicosilada del anexo requiere revisión técnica y no debe usarse para convertir resultados por su cuenta. | S2, pp. 11, 29 y 33 |
| RF-25 | Registrar vacuna y número de dosis aplicada, conservando las opciones del formulario y la casilla de otra vacuna. | Condicional: vacunación; usar esquema vigente y no marcar dosis no aplicadas. | S2, pp. 11 y 34 |
| RF-26 | Registrar diagnósticos ordenados: descripción, CIE-10 y tipo de ingreso P/D/R; egreso D/R cuando corresponda. La plantilla presenta cinco filas, sin exigir llenar las cinco en cada consulta. | General; egreso definitivo obligatorio en hospitalizados. | S2, pp. 34-35 |
| RF-27 | Imprimir nombres y apellidos, documento, categoría del responsable y colegiatura cuando corresponda; especialidad, RNE o marca de egresado según el caso. | General; especialidad/RNE condicional | S2, pp. 35-36 |
| RF-28 | Reservar espacios para firma y sello del responsable y firma/huella del asegurado o representante; imprimir nombres y documento del representante cuando corresponda. | FUA físico de salud, con excepciones normadas como telemedicina. Las reglas de prestaciones administrativas son distintas. | S2, pp. 7 y 36 |

## Datos del reverso

En el **primer nivel** estos bloques forman parte obligatoria del FUA. Los valores se completan conforme a lo prescrito, entregado, indicado o ejecutado. La directiva permite adecuar el listado preimpreso a la demanda, pero no suprimir sus campos. La alternativa de adjuntar un reporte de consumo descrita en el instructivo corresponde al segundo y tercer nivel.

| ID | Requerimiento | Datos por fila | Referencia |
| --- | --- | --- | --- |
| RF-29 | Imprimir productos farmacéuticos. | Código SISMED, nombre DCI, forma farmacéutica, concentración, cantidad prescrita, cantidad entregada y número del diagnóstico asociado. | S2, pp. 36-38 |
| RF-30 | Imprimir dispositivos médicos y productos sanitarios. | Código, nombre, presentación, características, cantidad prescrita, cantidad entregada y número de diagnóstico. | S2, p. 38 |
| RF-31 | Imprimir procedimientos, laboratorio y diagnóstico por imágenes. | Código CPMS, nombre, cantidad indicada, cantidad ejecutada, número de diagnóstico y resultado según corresponda. Aplicar obligatoriedad de resultados por procedimiento; no declarar ejecutado un examen pendiente. | S2, pp. 38-39; S3, p. 16, RC31 |
| RF-32 | Conservar el bloque de subcomponente prestacional/procedimientos. | Código, nombre, características, indicado/prescrito, ejecutado/entregado, diagnóstico, resultado, número de ticket y PO tal como figuran en el anexo. Su significado y uso deben resolverse con catálogo/regla SIS; no deducirlos de la abreviatura. | S2, p. 12 |
| RF-33 | Permitir observaciones resumidas y espacios de conformidad en el reverso. | Observación, firma y sello del responsable de farmacia/laboratorio/apoyo diagnóstico, y firma/huella del asegurado o representante; datos del representante cuando aplique. | S2, pp. 12 y 39 |

## Actualización necesaria para 2026

**RF-34.** Incorporar los códigos RM-CV en la casilla existente `COD. PRESTA.`, manteniendo el formulario oficial y el detalle del reverso. Aplican al primer nivel con convenio vigente SIS. Fuente: S3, pp. 5 y 11-17.

| Código | Curso de vida |
| --- | --- |
| 301 | Niño: desde RN hasta antes de cumplir 12 años |
| 302 | Adolescente: 12 hasta antes de cumplir 18 años |
| 303 | Joven: 18 hasta antes de cumplir 30 años |
| 304 | Adulto: 30 hasta antes de cumplir 60 años |
| 305 | Adulto mayor: 60 años o más |
| 306 | Cuidado integral de salud prenatal; validar condición materna y procedimiento conforme a su ficha |

**RF-35.** Aplicar reglas vigentes de correspondencia entre prestación, edad, condición, destino, diagnósticos, procedimientos, perfil profesional, consumo y resultados. El documento RM-CV modifica reglas existentes e incorpora otras; el sistema debe consultar sus fichas vigentes antes de codificar las validaciones. No elegir 301-306 automáticamente solo por edad ni convertir todos los códigos históricos. Fuentes: S3, pp. 15-17; S4.

## Requisitos de software e impresión propuestos

Estos son criterios técnicos recomendados para implementar los requisitos anteriores; no se presentan como especificaciones de impresora impuestas por la directiva.

| ID | Requerimiento propuesto | Criterio de aceptación |
| --- | --- | --- |
| RT-01 | Separar impresión del formulario completo e impresión de datos sobre papel preimpreso. | En modo preimpreso no repetir líneas, logos ni identificadores ya impresos. Usar el número de la hoja física, sin asignar silenciosamente uno diferente. |
| RT-02 | Tomar la geometría de la hoja realmente utilizada y conservar el anexo vigente. | Configurar tamaño, orientación, márgenes y coordenadas; comprobar ambos lados con la impresora de la posta. No afirmar tamaño A4 u oficio únicamente por el tamaño del PDF normativo. |
| RT-03 | Ofrecer vista previa y detectar texto fuera de casillas. | No recortar nombres, documentos, códigos ni resultados; mostrar el campo que requiere ajuste. |
| RT-04 | Mantener exactitud de códigos y fechas. | Conservar ceros iniciales y letras; separar fecha de atención de fecha de impresión; validar calendario y cronología; en este proyecto usar America/Lima. |
| RT-05 | Validar faltantes por prestación y distinguir impresión parcial de cierre del FUA. | Un borrador o prellenado parcial muestra pendientes. Para considerar completo el documento, exigir los datos y conformidades que correspondan. Confirmar un aviso no reemplaza una obligación normativa. |
| RT-06 | Reimprimir la misma atención sin emitir un número nuevo. | Mantener copia documental y versión de plantilla/reglas; una corrección posterior sigue un flujo trazable y no altera silenciosamente una versión ya conformada. |
| RT-07 | Relacionar medicamentos, dispositivos y procedimientos con diagnósticos del mismo FUA. | `DX` referencia una fila válida; las cantidades prescritas/indicadas se distinguen de las entregadas/ejecutadas; los resultados reflejan lo realmente obtenido. |
| RT-08 | Manejar capacidad de filas sin pérdida de información. | Si excede la plantilla, advertir y usar el procedimiento autorizado por la red/UDR. No aplicar a postas por defecto la excepción de reporte de consumo de segundo/tercer nivel. |
| RT-09 | Mantener catálogos y reglas con versión y vigencia. | Registrar fuente de RENIPRESS, prestaciones, UPS, CIE-10, CPMS, SISMED, etnias y vacunas; impedir códigos locales presentados como oficiales. |
| RT-10 | Proteger la información del paciente y registrar operaciones. | Acceso por rol; registro de creación, corrección y reimpresión; calibración sin datos clínicos en almacenamiento del navegador; FUA físico incorporado a la historia clínica y disponible para control. |
| RT-11 | Distinguir firmas pendientes, firma manuscrita y firma digital. | No insertar automáticamente imágenes de firma o huella como conformidad. Una impresión/PDF generado no se presenta como FUA digital firmado. |
| RT-12 | Tratar FUA digital como alcance específico si se solicita. | Todos los componentes, firma digital del responsable, código único de acreditación SITEDS y repositorio que garantice disponibilidad, integridad y confidencialidad; definir además integración SETI-SIS según su proceso. Fuentes: S2, pp. 7-8 y 23; S5. |

## Orden sugerido para este proyecto

1. **Prioridad 0:** plantilla vigente, identificación/afiliación, número coordinado con la autoridad, atención/prestación/UPS, diagnósticos, responsable y espacios de conformidad; cubrir ambos lados y validaciones de la prestación seleccionada.
2. **Prioridad 1:** cerrar el detalle de medicamentos, dispositivos, laboratorio y procedimientos, destino/referencias y las actividades preventivas/maternas/infantiles que efectivamente ofrece la posta; incorporar RM-CV y sus reglas.
3. **Prioridad 2:** robustecer calibración, reimpresión, correcciones y catálogos; implementar FUA digital e integración externa si forman parte del alcance acordado.

Las prioridades organizan el trabajo, no permiten omitir en producción un campo obligatorio para una prestación que la posta brinda.

Según la documentación existente `docs/FUA_IMPRESION.md`, el módulo actual realiza **prellenado parcial**: ya dispone de datos básicos de paciente, sede, responsable y ciertas mediciones, pero declara pendientes prestaciones, diagnósticos, vacunas, hospitalización, destinos, datos RN y varios preventivos. Este documento no certifica cobertura actual: el cotejo mencionado es documental, no una auditoría exhaustiva del código ni una prueba física.

## Casos de aceptación para revisar con la posta

- Consulta ordinaria: anverso con identidad, afiliación, prestación, UPS, diagnóstico y responsable; reverso consistente con lo realmente realizado.
- Medicación parcialmente entregada: imprimir cantidades prescrita y entregada distintas y vinculadas al diagnóstico correcto.
- Laboratorio solicitado y todavía pendiente: conservar la indicación sin inventar ejecución o resultado; vincular FUA si el supuesto oficial lo exige.
- Atención integral infantil RM-CV: código 301 apropiado, CRED y demás intervenciones realizadas, con detalle CPMS/consumo; conservar diseño oficial.
- Salud materna: condición y FPP/fecha real correctas, controles y datos RN cuando correspondan, según prestación/reglas vigentes.
- Referencia de ingreso y salida: origen y destino en sus respectivos bloques, sin intercambiarlos.
- Reimpresión: mismo número y datos documentales; ningún nuevo registro de atención o correlativo.
- Hoja preimpresa: el número físico coincide en ambos lados y con la copia del sistema; alineación comprobada físicamente, sin recortes ni doble impresión.

Para convertir esta lista en configuración de producción falta concretar la categoría, cartera de servicios, convenio, rango de FUA y hoja física de la IPRESS. Estos datos definen cuáles de los requisitos condicionales se activan.
