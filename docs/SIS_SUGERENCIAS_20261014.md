# Sugerencias SIS en alta y admisión

## Evidencia y significado

Se leyeron los catálogos públicos EESS/EESS_SIS y configuraciones fua/fua2/fua3 del
origen ETLSIS, y se contaron los campos de afiliación de Pacientes sin extraer identidades.
Las seis sedes reales del catálogo tienen `EESS.Clave=040`: DIRESA Arequipa.
`fua.8_Cod_eess=2` pertenece a la configuración del número de FUA, no al formato de
afiliación. `EESS_SIS.Codigo=002..006` son claves del catálogo de planes, no valores que
deban recortarse para llenar Tipo.

Los campos individuales del origen son `Arequipa_040`, `Arequipa_2` y `Arequipa_SIS`.
Entre los registros de Afiliación Temporal, 302 llevan `E` y uno `2`; NRUS tiene 222 `R`
y uno `8`. Gratuito/Para Todos incluyen formatos `2` y `3`. El origen contiene
excepciones y valores dañados: la frecuencia no constituye una regla individual.

La copia local de la [Directiva FUA V.02](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j),
PDF p. 19, describe: `2` subsidiado/DNI, `3` subsidiado/CE, `E` temporal, `R` NRUS,
`9` Independiente, `8` Microempresas. Se contrastó el texto conservado en
`tmp/pdfs/sis-fua-v02.txt`; en esta ejecución el sitio oficial respondió 403/418.

## Comportamiento

| Selección | Sugerencia en el borrador |
| --- | --- |
| Sede con código DIRESA y plan SIS | Código DIRESA de la sede, por ejemplo 040 |
| Afiliación Temporal | Tipo E |
| NRUS | Tipo R |
| Gratuito/Para Todos + DNI | Tipo 2 |
| Gratuito/Para Todos + CE | Tipo 3 |
| SIS genérico / Semi subsidiado / documento no identificable | Sin formato inferido |
| Distrito o Localidad | No cambian la afiliación; son residencia |

Alta y admisión comparten `useSisAffiliationDefaults`. Una corrección manual, incluso
dejar una casilla vacía, se conserva durante el borrador. Para Gratuito/Para Todos,
el tercer campo copia el documento válido: DNI de ocho dígitos o CE numérico de
ocho/nueve, siguiendo el instructivo (p. 20) y el contrato numérico vigente de la API.
Se actualiza al editar el documento; mantiene los ceros iniciales y las correcciones
manuales. Una copia automática se retira si deja de corresponder al plan/formato.
Temporal y NRUS conservan su número específico, sin deducirlo del DNI. La secuencia
no se inventa. No se utiliza el ID de la sede ni del seguro como código SIS.

Abrir admisión no modifica los códigos confirmados ni genera cambios pendientes. Un
cambio explícito de plan recalcula su formato salvo corrección manual en el borrador.
Un cambio de sede actualiza la DIRESA sugerida si coincide con la sugerencia anterior;
se conserva una DIRESA diferente guardada, pues el asegurado puede proceder de otra
región. Se espera a que llegue el catálogo antes de calcular. Abrir la ficha no
autocompleta vacíos confirmados; las sugerencias se aplican a los cambios del borrador.

Descartar restaura lo guardado. Registrar/Guardar conserva las sugerencias o correcciones
mediante el contrato existente de la API. El servidor sigue validando la afiliación y no
añade valores inferidos. La atención/FUA sigue copiando el contrato confirmado de la
ficha mediante sus snapshots; esta revisión no modifica copias históricas.

## Verificación en navegador

- Usuario médico, alta: sede Alto Selva Alegre + Afiliación Temporal → 040/E con número
  y secuencia vacíos; no se registró un paciente de prueba en la base de uso.
- `/admision?patientId=14`: cambiar a Temporal → E en borrador; descartar → contrato
  original 040/2 y plan original restaurados. No se pulsó Guardar paciente ni Guardar atención.
- Cambiar residencia a Cayma limpia localidad y conserva la afiliación; después se descartó.
- Sin errores de consola en la revisión de admisión.
- Evidencia: `docs/audits/patient-sis-defaults-20261014.jpg`.

Validación final: 45 pruebas frontend aprobadas (reglas de sugerencias, alta,
admisión y editor de laboratorio), compilación/tipos y lint aprobados. Las pruebas
comprueban el payload de Registrar/Guardar, los ceros iniciales, edición manual,
residencia independiente, espera del catálogo y restauración de códigos confirmados.

## Tercer campo dinámico desde documento

Se agregó el número de documento a las dependencias de las sugerencias compartidas.
Gratuito/Para Todos copian el DNI/CE compatible y lo actualizan al escribir o cambiar
el tipo de documento. Mientras el valor está incompleto, se retira la copia automática;
al completarse se vuelve a sugerir. Se conserva un número de afiliación distinto
guardado o corregido manualmente. Al cambiar a un plan sin esta regla se limpia
solo la copia automática, sin inventar una afiliación nueva. Secuencia/RN permanece
independiente.

Comprobaciones: 10 pruebas de reglas y 41 de alta/admisión/laboratorio aprobadas;
compilación, tipos y lint aprobados. Navegador con usuario médico: en alta,
DNI ficticio `00112233` → `00445566` actualiza el número SIS; en el borrador del
paciente 14 con Gratuito, editar el DNI actualiza la afiliación, y descartar restaura
ambos datos y el plan original. No se guardó un paciente ni una atención de prueba.
Evidencia: `docs/audits/patient-sis-document-number-20261014.jpg`.
