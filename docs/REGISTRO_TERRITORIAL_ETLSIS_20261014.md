# Distrito, localidad y establecimiento en Nuevo paciente

Revisión del 14/10/2026 de `/pacientes/nuevo`, contra el snapshot ACE y el archivo original
`etlSis/private/source.mdb`. El origen se leyó sin modificarlo; se comprobó su huella SHA-256.
Se analizaron catálogos y recuentos anónimos, sin publicar identidades de pacientes.

## Qué demuestra el origen

- `Provincia` contiene 29 distritos. Su `Codigo` identifica la tabla `Z_XX` correspondiente,
  pero no es el UBIGEO: Alto Selva Alegre tiene `Codigo=1`, tabla `Z_01`, y UBIGEO **040102**.
- Las tablas `Z_01…Z_29` contienen sugerencias de localidades por distrito. Por ejemplo,
  Cayma (`Z_02`) ofrece 11 DE MAYO, 30 DE MARZO y ACEQUIA ALTA; Cercado (`Z_03`) ofrece
  CERCADO, COOP. UNIVERSITARIA y LA NEGRITA.
- `Pacientes.Distrito`, `Pacientes.Localidad` y `Pacientes.Establecimiento` son campos de texto
  separados. Localidad no era un vínculo obligatorio a una fila del catálogo.
- La configuración `fua` guarda distrito ALTO SELVA ALEGRE, tabla Z_01 y localidad general
  ALTO SELVA ALEGRE. Esa localidad general no aparece exactamente así entre los 88 barrios
  de Z_01: existen las variantes A, B y C, entre otros sectores.
- En los 73.209 registros del snapshot, 62.593 usan como localidad el nombre general del
  distrito. 66.924 localidades no coinciden con la lista del distrito; 5.679 sí coinciden.
  Esos recuentos no demuestran cada interacción de la aplicación original, pero sí demuestran
  que limitar el registro a las filas Z_* impediría representar muchos datos del legado.
- Hay 444 registros con un distrito reconocido diferente de Alto Selva Alegre y una de las
  seis sedes conocidas de esa zona. Por tanto, filtrar la sede de inscripción según el domicilio
  cambiaría el comportamiento representado en el origen.

El lector disponible no expuso las definiciones de las consultas ni los eventos del formulario
original. Esta revisión distingue evidencia de datos/configuración de una reconstrucción de UI.

## Corrección del error de códigos

La interpretación anterior fue incorrecta: **`Z_XX.Codigo` no equivale a `Z_XX.Clave`**.
La migración 0018 había llamado `codigo_sis` al código interno consecutivo del catálogo.
La revisión 0034 corrigió el salto 0050→0052, pero seguía tratándolo con ese nombre incorrecto.

Ahora se guardan por separado:

| Dato | Significado | Ejemplo de PORTALES DEL MIRADOR |
| --- | --- | --- |
| `id` | Identificador de la localidad en esta aplicación | Se conserva |
| `codigo_catalogo` | `Codigo` de la tabla Z_* del distrito | 0052 |
| `codigo_sis` | Valor numérico de `Clave` conservado del legado | 00000001 |

La Clave puede repetirse: los 88 barrios de Z_01 llevan **00000001**. En Cayma está ausente
(`-`); se guarda como NULL. Se recuperaron 199 claves numéricas de ocho caracteres del origen;
las demás permanecen sin clave. Se conserva el valor de origen, sin afirmar una homologación
actual ante SIS ni inventar códigos para localidades escritas.

La revisión `20261014_0036_locality_keys` conserva los IDs y nombres, cambia la restricción de
unicidad para que corresponda a distrito/código interno, y separa las claves de exportación.
Respaldo: `tmp/localidades_before_0036.json`. Las huellas de pacientes e historial/FUA antes
y después son iguales; las copias históricas anteriores no se reescribieron.

## Cómo queda la pantalla

1. **Distrito:** lugar donde reside el paciente. Se cargan los 29 distritos completos;
   la carga anterior traía solo los primeros 25.
2. **Localidad:** puede elegirse el nombre general del distrito, una sugerencia del catálogo,
   o escribirse otro nombre. Una sugerencia conserva su ID; un nombre escrito se guarda como
   texto sin inventar una fila ni una clave de exportación.
3. **Dirección:** dirección del domicilio dentro de esa residencia.
4. **Establecimiento:** sede donde se registra al paciente. Su ubicación física y la residencia
   del paciente permanecen independientes.

Al cambiar de distrito se limpia la localidad anterior; la sede se conserva. Se retiraron los
códigos internos del texto visible de las opciones y se aclararon los placeholders. Las búsquedas
descartan respuestas antiguas, conservan las opciones seleccionadas y recorren todas las páginas.
El editor compartido de admisión también muestra y permite corregir localidades de texto del legado.

Las nuevas copias clínicas guardan versión 2 del contexto, incluyendo código interno y clave de
exportación como datos distintos. El flujo clínico Consultorio → Servicio/especialidad → Profesional
conserva sus tres selectores.

## Comprobación

- 412 pruebas unitarias backend aprobadas.
- 46 pruebas MySQL aprobadas en una base nueva y desechable: migración, claves compartidas,
  localidad escrita, paciente, atención, historial y emisión FUA.
- 33 pruebas frontend de registro, editor y localidades aprobadas.
- Compilación de producción, tipos y lint de los cambios aprobados.
- Catálogo local comprobado con `medico.demo`: 29 distritos y 88 localidades de Alto Selva
  Alegre, con códigos internos únicos y clave de exportación compartida.
- UI comprobada en la ruta solicitada: localidad general, localidad escrita, cambio de distrito
  y sede conservada. No se creó un paciente real durante la inspección de pantalla.
- Evidencia: `docs/audits/patient-registration-territory-20261014.jpg`.

Auditoría reproducible del origen: `tmp/audit_registration_source.py`.

## Verificación del alta, etnia y marca del seguro

Se comprobó el contrato del formulario y el recorrido API → MySQL → atención → historial →
FUA con un paciente ficticio en una base de pruebas nueva y desechable. El UBIGEO `040102`,
el ID de localidad y la sede de registro se guardan por separado. Para PORTALES DEL MIRADOR,
el contexto clínico y territorial del FUA conserva `codigo_catalogo=0052` y
`codigo_sis=00000001`; no sustituye estos códigos por el ID de la localidad.
La afiliación `040 / 02 / 001122334 / 01` conserva sus ceros iniciales en la ficha y en el FUA.
La etnia seleccionada (`58` en la prueba) también se guarda y llega al FUA.

La etnia quedó visible fuera de «Datos adicionales», con el catálogo cargado desde el inicio
y el aviso/reintento también visibles si falla la carga. Arranca «Sin declarar»: no se asigna
una etnia a todos los pacientes automáticamente.
«Seguro de salud» reutiliza `PatientInsuranceBrand`, igual que admisión, con logos de SIS y
EsSalud e iconos para las demás categorías según el código/régimen del catálogo.

Comprobaciones adicionales de esta revisión:

- 47 pruebas MySQL aprobadas; la prueba nueva incluye ceros, códigos territoriales,
  cambio posterior de seguro, etnia conservada y FUA/historial anterior intacto.
- 43 pruebas frontend aprobadas entre registro, marcas de seguro y editores de admisión/laboratorio
  (17 de registro y 26 de los otros tres archivos).
- Compilación, comprobación de tipos y lint de los componentes y pruebas modificados aprobados.
- Navegador en `/pacientes/nuevo` con `medico.demo`: etnia visible sin abrir el desplegable,
  logos SIS/EsSalud cargados, icono de Otro, afiliación limpiada al cambiar a EsSalud y etnia
  conservada. Sin errores de consola ni desbordamiento horizontal a 1280 px.
- No se registraron pacientes de prueba en la base de uso durante la inspección de pantalla.
- Evidencia: `docs/audits/patient-registration-codes-20261014.jpg`.
