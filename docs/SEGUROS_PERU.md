# Seguros, marcas y códigos en la ficha del paciente

Revisión de fuentes oficiales: 12 de octubre de 2026.

## Marca según el seguro

`PatientInsuranceBrand.vue` recibe el registro del catálogo seleccionado por
`seguro_id`. Usa `regimen` y `codigo` para identificar la entidad; el ID numérico
de la base de datos no determina la marca. Se reutiliza en admisión y laboratorio.
En admisión sigue el borrador, vuelve al valor original al descartar y conserva
el resultado devuelto por la API al guardar. Laboratorio muestra el seguro guardado.

- SIS y sus planes usan el logo publicado en la [ficha oficial de SIS](https://www.gob.pe/sis).
- EsSalud usa el logo publicado en la [ficha oficial de EsSalud](https://www.gob.pe/essalud).
- Sanidad, Particular, Otro y Sin seguro usan distintivos de icono y etiqueta. Esas categorías no
  identifican una entidad única; no se les atribuye un logo de SALUDPOL, de una
  fuerza armada o de una aseguradora privada.
- Un dato nulo muestra «Sin registro». Un ID sin catálogo disponible muestra
  «Seguro», sin atribuir una marca. Si falla una imagen, se conserva su nombre.

Todos los distintivos ocupan un marco de 90 × 52 px, incluidos estados sin
registro y errores de imagen. Los iconos genéricos proceden de la biblioteca
Element Plus de la aplicación y no representan emblemas institucionales.
El bloque de seguro reserva su altura para evitar saltos al cambiar de categoría.
Los PNG se sirven desde el propio frontend y mantienen sus proporciones y colores.
Las casillas de afiliación SIS solo se muestran para seguros SIS.

## Tres códigos diferentes

| Dato | Significado | Fuente |
| --- | --- | --- |
| `seguros.id` / `pacientes.seguro_id` | Relación interna con el catálogo | Base de datos de esta aplicación |
| `seguros.codigo_sis` | Código del catálogo histórico `EESS_SIS`, conservado por el ETL | `Data_base.mdb` / migración `20260924_0018_sis_localities` |
| Financiador HIS MINSA | Quién financia una atención | Catálogo de la hoja HIS |

Los valores históricos `001–009` **no son equivalentes** al financiador HIS:
por ejemplo, EsSalud es `007` en el origen ETLSIS y `3` en HIS; el `2` de HIS
representa SIS en general, no solamente SIS Gratuito.

La [guía oficial de registro HIS publicada por DIRESA Piura](https://www.diresapiura.gob.pe/documentos/Manuales/RegistroHISMINSA2017.pdf),
ítem 9 (página 8), distingue los siguientes financiadores:

| Código HIS | Financiador |
| --- | --- |
| 1 | Usuario / pagante |
| 2 | SIS |
| 3 | EsSalud |
| 4 | SOAT |
| 5 | Sanidad FAP |
| 6 | Sanidad Naval |
| 7 | Sanidad Ejército |
| 8 | Sanidad PNP |
| 9 | Privados |
| 10 | Otros |
| 11 | Exonerado |

Esto documenta la codificación de esa guía; no certifica la integración de esta
aplicación con HIS ni la vigencia de todos sus catálogos a nivel nacional.
Una exportación HIS debe validar el catálogo exigido por el receptor. El dato
actual «Sanidad (FFAA / Policía)» no permite elegir entre 5, 6, 7 y 8, y «Sin
seguro» por sí solo no acredita que una atención sea pagante o exonerada.

## Código de afiliación del asegurado SIS

La [Trama de datos del FUA publicada por SIS en 2025](https://www.gob.pe/institucion/sis/informes-publicaciones/7041412-trama-de-datos-del-fua)
([PDF oficial](https://cdn.www.gob.pe/uploads/document/file/8491198/7041412-documentotramadatos.pdf?v=1755189947)),
página 9, define los datos del contrato:

| Campo local | Campo de acreditación SIS | Forma |
| --- | --- | --- |
| `sis_diresa` | `contratoDisa` / `afi#25` | 3 caracteres, condicional según contrato |
| `sis_tipo` | `contratoFormato` / `afi#26` | 1 o 2 caracteres alfanuméricos |
| `sis_numero` | `contratoNumero` / `afi#27` | 8 o 9 dígitos, conservando ceros iniciales |
| `sis_secuencia` | `contratoSecuencia` / `afi#28` | Hasta 2 dígitos, condicional según contrato |

La estructura de las casillas de la aplicación coincide con esos tamaños.
Los valores deben provenir de la acreditación individual: no se deduce
`sis_tipo` recortando el código ETLSIS del plan ni se reemplaza `sis_diresa`
con la DISA de la sede de registro como si fuera una acreditación verificada.
El backend no infiere el contrato desde esas selecciones. Desde la revisión
del 14/10/2026, alta y admisión ofrecen sugerencias **editables en el borrador**:
DIRESA de la sede y formato según la Directiva FUA V.02 (p. 19): `E` temporal,
`R` NRUS, `2` subsidiado/DNI y `3` subsidiado/CE en Gratuito/Para Todos.
No se deduce un formato de «SIS» genérico o «Semi subsidiado», que no identifica
por sí solo Independiente (`9`) frente a Microempresas (`8`).
Un cambio explícito de plan recalcula el formato, salvo corrección manual en
el borrador. Una DIRESA guardada distinta de la sugerencia anterior se conserva,
pues la persona puede estar afiliada en otra región. Distrito y localidad son
residencia y no recodifican el contrato. Abrir una ficha no modifica sus códigos;
«Descartar cambios» restaura los confirmados. Para Gratuito/Para Todos, el número
sigue el DNI/CE numérico válido en el borrador, conservando ceros y correcciones
manuales (Directiva FUA V.02, p. 20). Temporal y NRUS mantienen su número de
afiliación específico. La secuencia nunca se inventa.
Solo Registrar/Guardar persiste las selecciones y correcciones. Cambiar a un
seguro no SIS limpia la afiliación actual. No se modificaron retrospectivamente
pacientes ni FUAs históricos.

Esta revisión abarca las casillas de afiliación y las marcas, no una certificación
completa de la trama FUA. La acreditación real y su vigencia requieren datos del SIS.
