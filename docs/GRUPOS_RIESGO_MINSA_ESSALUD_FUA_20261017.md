# Grupos de riesgo: MINSA, EsSalud y FUA

Revisión documental y de código: 17 de octubre de 2026, America/Lima.

## Decisión que orienta el ajuste

El selector actual no debe convertirse en una lista que mezcle diagnósticos nutricionales, resultados de tamizaje y categorías de vacunación. Las fuentes revisadas no presentan un catálogo único de «grupo de riesgo del paciente» equivalente a nuestras cuatro etiquetas heredadas de ETLSIS.

Recomiendo separar **valoración por atención**, **riesgo identificado con un método**, **diagnóstico clínico** y **seguimiento longitudinal**. El cálculo puede automatizarse; la interpretación clínica, la codificación y el inicio/cierre del seguimiento deben quedar identificados con el profesional y su decisión. Esta es una propuesta de implementación, no una transcripción de un modelo de datos oficial.

Esta revisión describe lo establecido en documentos oficiales y un ejemplo del SIHCE MINSA; no es una observación presencial de todas las postas. No se modificaron reglas clínicas, catálogos ni pacientes durante esta investigación.

## Cómo se evalúa y clasifica

### Niños: atención CRED en MINSA

La NTS 238-MINSA/DGIESP-2025, aprobada por RM 682-2025/MINSA, incluye CRED hasta los 11 años, 11 meses y 29 días. Diferencia la condición de crecimiento de la clasificación nutricional. La evolución entre controles puede generar una alerta aunque la medición aislada esté dentro de límites normales. Se registran hallazgos, interpretación y acciones en la historia clínica, con intervención y seguimiento según evaluación profesional. Véanse pp. 26 y 28–31 del PDF [S1].

La guía RM 034-2024/MINSA desarrolla las alertas por cambios de tendencia en P/E, P/T y T/E. Diferencia riesgo de desnutrición, riesgo de sobrepeso y riesgo de talla baja; exige considerar antecedentes, dirección de la curva y periodo de control. El manual SIHCE CRED muestra, por separado, la clasificación nutricional y las respuestas sobre ganancia inadecuada de peso o talla [S2, S3]. No conviene sustituir esta evaluación por la regla «un Z alterado = asignar un grupo permanente».

| Población | Clasificación antropométrica que debe distinguirse del riesgo |
| --- | --- |
| Menores de 5 años | P/E: normal, bajo peso, bajo peso severo y sobrepeso según tabla MINSA. P/T: normal, bajo peso/emaciado, bajo peso severo, sobrepeso y obesidad. T/E: normal, talla baja, talla baja severa y alto. |
| De 5 años a 11 años, 11 meses y 29 días | IMC/edad: normal, delgadez, delgadez severa, sobrepeso y obesidad. T/E: normal, talla baja, talla baja severa y talla alta. |
| Adolescentes | IMC/edad y T/E, con sus referencias por edad y sexo; no corresponde aplicar sin más el IMC adulto. |

Fuentes: tabla 3 de [S1], cuadros 6–14 de [S2] y cuadros 1–2 de [S4]. P/E disponible en una biblioteca OMS fuera del grupo infantil no lo convierte automáticamente en el indicador principal requerido por la norma peruana para escolares o adolescentes.

### Adultos y adultos mayores: MINSA

La guía RM 184-2012/MINSA diferencia clasificación por IMC y riesgo asociado al perímetro abdominal. Ambos resultados se registran en la historia clínica; el registro HIS tiene su propia codificación [S5].

| IMC adulto | Clasificación antropométrica |
| --- | --- |
| <16 | Delgadez grado III |
| 16 a <17 | Delgadez grado II |
| 17 a <18.5 | Delgadez grado I |
| 18.5 a <25 | Normal |
| 25 a <30 | Sobrepeso |
| 30 a <35 | Obesidad grado I |
| 35 a <40 | Obesidad grado II |
| ≥40 | Obesidad grado III |

La guía RM 240-2013/MINSA usa otros límites en adultos mayores: delgadez ≤23; normal >23 a <28; sobrepeso ≥28 a <32; obesidad ≥32. También contempla una ficha para valorar riesgo de malnutrición y evaluación integral [S6, pp. 13, 24–27 impresas / 15, 26–29 del PDF].

En adultos y adultos mayores, el perímetro abdominal diferencia riesgo bajo, alto y muy alto: varones <94, 94 a <102 y ≥102 cm; mujeres <80, 80 a <88 y ≥88 cm [S5, S6]. Es un riesgo diferente del déficit nutricional. Gestantes y puérperas necesitan su contexto materno; no propongo aplicarles de forma indiscriminada esta tabla.

### EsSalud: tamizaje de desnutrición

La GPC IETSI 46-2021 propone MST o MUST y considera MNA-SF en mayores de 60 años. El ámbito descrito incluye adultos ambulatorios u hospitalizados en hospitales de nivel II y III; no debe presentarse como exigencia general de toda posta MINSA [S7, pp. 6–7 y 18 impresas / 9–10 y 21 del PDF].

| Instrumento | Resultado de tamizaje |
| --- | --- |
| MUST | 0: riesgo bajo; 1: intermedio; ≥2: alto. |
| MST | 0–1: sin riesgo según ese instrumento; ≥2: en riesgo. |
| MNA-SF | 12–14: normal; 8–11: riesgo; 0–7: malnutrición según el cribaje. |

Estas herramientas requieren datos adicionales al peso y talla: por ejemplo pérdida involuntaria de peso, ingesta/apetito y otros componentes propios del instrumento. Un resultado positivo conduce a evaluación e intervención; no equivale por sí solo a una codificación diagnóstica automática. En nuestra aplicación falta una captura estructurada de estos tamizajes.

## ¿Debe ir el riesgo en el FUA?

**El FUA no contiene una casilla genérica para imprimir las etiquetas nutricionales del paciente.** El anexo 1 muestra **Grupo de riesgo HVB** dentro de vacunación, con categorías como personal y estudiantes de salud. Esa casilla no corresponde a desnutrición, talla baja ni riesgo cardiometabólico [S8, p. 11].

Los problemas atendidos que el profesional registre como diagnósticos se consignan en la sección de diagnósticos, con descripción, CIE-10 y tipo P/D/R. También se documentan las prestaciones y actividades realmente realizadas. Por tanto, un riesgo o condición puede formar parte del registro asistencial pertinente, pero no se copia todo el historial de grupos al FUA ni se convierte automáticamente una etiqueta en enfermedad [S8, pp. 29 y 34–37].

La RG 000002-2026-SIS/GREP incorpora registro modular por curso de vida, con códigos 301–306, desde el 01/03/2026. Mantiene la estructura del FUA V.02. Debe revisarse esa codificación antes de automatizar prestaciones para una posta [S9, p. 17]. La guía clínica EsSalud no sustituye las reglas de registro SIS.

## Qué encontramos en el sistema actual

| Hallazgo comprobado | Consecuencia para el ajuste |
| --- | --- |
| La migración 0023 solo agrega cuatro etiquetas ETLSIS. | Conservarlas como legado; no anunciarlas como catálogo nacional completo ni convertirlas masivamente en diagnósticos actuales. |
| `PatientRisk` conserva paciente, grupo, inicio, fin y observación. | Es un historial de periodos, pero no registra de forma estructurada instrumento, puntaje, versión normativa, atención de origen ni decisión profesional. |
| `calculate_nutritional_indicators` calcula la atención con las medidas actuales. | No determina las tendencias de crecimiento requeridas para valorar ciertos riesgos infantiles. |
| Para T/E Z=+2.5, `classify_score` devuelve «Normal»: talla alta empieza en >+3. | Las tablas MINSA revisadas consideran alto/talla alta en >+2. Debe ajustarse la clasificación antes de asociar grupos. |
| A los 5 años exactos la prueba del motor devolvió INFANTIL, sin IMC/edad; poco después devolvió SIN_REFERENCIA hasta alcanzar 61 meses aproximados. | Revisar transición desde los 5 años y disponibilidad de tablas; no inventar puntajes durante el intervalo. |
| En adultos, el motor devuelve «Bajo peso» sin grados y «Obesidad» sin grados. | Si se adopta la presentación MINSA, completar los grados sin modificar retrospectivamente resultados históricos. |
| El motor ya diferencia los límites de IMC de adultos mayores. | Conservar esa diferenciación; no reutilizar el umbral adulto 18.5 en mayores. |
| No se encontró un cálculo estructurado de MST, MUST o MNA-SF en el flujo actual. | El sistema no puede afirmar un resultado de esos instrumentos solo porque tenga IMC. |
| El resumen FUA guarda textos nutricionales, pero las posiciones de impresión no incluyen diagnósticos CIE-10 ni grupo HVB. | Mostrar un «Dx IMC» en el resumen no significa haber llenado la sección oficial de diagnósticos. Completar esa integración es un trabajo propio. |

La comparación ejecutada está en `tmp/riesgos-normativa-20261017/comparacion-motor.json`. Fueron llamadas al dominio con datos ficticios, sin registrar atenciones. El ejemplo adulto previo de IMC 16.327 corresponde a **delgadez grado II por la tabla antropométrica MINSA**; esa clasificación no autoriza por sí sola a elegir un código de desnutrición clínica.

## Propuesta concreta de implementación

Esta sección es recomendación de diseño del sistema, diferenciada de las disposiciones oficiales.

### 1. Corregir la base clínica antes de ampliar el selector

Establecer un perfil de clasificación por norma y versión. Revisar primero límites de edad, T/E, etiquetas de P/E, grados del IMC adulto y disponibilidad de IMC/edad escolar. Distinguir resultado antropométrico de alerta de tendencia y diagnóstico. Conservar valor calculado y referencia usados en cada atención; una actualización no debe reescribir silenciosamente lo histórico.

### 2. Estructurar la evaluación de riesgo

Registrar, según el método aplicable:

- Dominio y método: crecimiento infantil, MUST, MST, MNA-SF u otro protocolo aprobado por la IPRESS.
- Respuestas/medidas necesarias, fecha, fuente de los datos y versión del instrumento.
- Puntaje y categoría propios de ese método, sin convertir todas las escalas a un «alto/medio/bajo» universal.
- Profesional, atención de origen, interpretación y acciones.

Mantener estados distintos para **no evaluado**, **datos insuficientes**, **no aplica** y **evaluado**. Un formulario incompleto nunca debe generar «sin riesgo». En el primer control infantil, distinguir el resultado actual de una tendencia que todavía no puede establecerse con el historial disponible.

### 3. Generar sugerencias y confirmar el seguimiento

El servidor puede sugerir una alerta cuando existan datos suficientes y una regla identificada. El profesional confirma su interpretación y el seguimiento. Registrar la cita próxima, derivación/interconsulta, responsable y motivo de cierre o recuperación.

Los periodos actuales pueden conservarse para seguimiento, vinculándolos con la evaluación que los originó. Una medición normal posterior no debe cerrar automáticamente todos los riesgos. En la pantalla conviene mostrar «Sin seguimiento vigente registrado» en vez de una expresión que pueda interpretarse como «sin riesgo clínico».

### 4. Separar el catálogo por finalidad

Como mínimo, separar nutrición/crecimiento de inmunizaciones-HVB. Si más adelante se incluyen riesgos obstétricos, cardiometabólicos o familiares, cada dominio requiere su protocolo y datos propios. Las condiciones ya diagnosticadas deben relacionarse con los diagnósticos de la atención y no ocultarse bajo una opción genérica «riesgo».

No crear una equivalencia automática entre las cuatro etiquetas ETLSIS y los códigos oficiales. La homologación necesita revisión semántica, fuente y contexto. Los datos antiguos deben conservar su denominación de origen.

### 5. Integrar el FUA por atención

Usar los diagnósticos pertinentes confirmados por el profesional, su código y tipo, junto con las prestaciones/procedimientos realmente efectuados. La categoría HVB, cuando corresponda, debe capturarse en inmunizaciones y con su catálogo propio, sin deducirla de riesgos nutricionales, sexo, etnia o apariencia.

Conservar la copia por atención que ya tiene el sistema. Cambiar el seguimiento actual del paciente no debe alterar un FUA anterior. La codificación HIS y la codificación/consistencia SIS deben tratarse explícitamente; no asumir que todo código de una guía histórica puede volcarse sin revisión a una casilla del FUA vigente.

### Orden de trabajo sugerido

1. Perfil MINSA y correcciones del motor; pruebas en límites de edad y valores de corte.
2. Evaluación nutricional estructurada y tendencias con historial suficiente.
3. Confirmación y seguimiento, con trazabilidad de la decisión.
4. Diagnósticos/prestaciones y su proyección al FUA.
5. Módulo HVB separado si el alcance incluye inmunizaciones.

## Fuentes oficiales y páginas verificadas

Las páginas PDF cuentan desde la primera hoja del archivo. Las páginas impresas pueden diferir. Las tablas relevantes se renderizaron y revisaron visualmente, además de extraer texto. Copias, capturas, extracción y registro de huellas en `tmp/riesgos-normativa-20261017/`.

| ID | Documento / fuente oficial | Páginas PDF consultadas |
| --- | --- | --- |
| S1 | [NTS 238-MINSA/DGIESP-2025, edición publicada 2026](https://cdn.www.gob.pe/uploads/document/file/9598727/7857089-norma-cred-12-03-26.pdf) | 26, 28–31, 38–39 y 188 |
| S2 | [RM 034-2024/MINSA: valoración antropométrica de 0 a 11 años](https://cdn.www.gob.pe/uploads/document/file/5698810/5059776-resolucion-ministerial-n-034-2024-minsa.pdf) | 11–16 y 18 |
| S3 | [Manual oficial SIHCE: CRED](https://www.minsa.gob.pe/sihce/manualess/MU_CRED.pdf) | 32, ejemplo de registro; no reemplaza la norma clínica |
| S4 | [RM 283-2015/MINSA: valoración de adolescentes](https://cdn.www.gob.pe/uploads/document/file/390257/guia-tecnica-para-la-valoracion-nutricional-antropometrica-de-la-persona-adolescente.pdf) | 20 y 43; clasificación y distinción del registro HIS |
| S5 | [RM 184-2012/MINSA: valoración de adultos](https://spij.minjus.gob.pe/Graficos/Peru/2012/Marzo/17/RM-184-2012-MINSA.pdf) | 1, 4, 9–12 y 17 |
| S6 | [RM 240-2013/MINSA: valoración de adultos mayores](https://bvs.minsa.gob.pe/local/MINSA/2858.pdf) | 15, 26–30 |
| S7 | [EsSalud IETSI: GPC desnutrición del adulto, versión corta](https://ietsi.essalud.gob.pe/wp-content/uploads/2021/12/GPC-Malnutricion_Version-corta.pdf), [ficha institucional](https://repositorio.essalud.gob.pe/handle/20.500.12959/2182) | 9–10 y 21 |
| S8 | [SIS: Directiva 002-2024-SIS/GREP-V.02](https://cdn.www.gob.pe/uploads/document/file/7310926/6245149-directiva-n-02-2024-sis-grep-v-02-actualizado.pdf), aprobada por [RJ 000178-2024-SIS/J](https://www.gob.pe/institucion/sis/normas-legales/6245149-000178-2024-sis-j) | 11, 29 y 34–37 |
| S9 | [SIS: RG 000002-2026-SIS/GREP](https://www.gob.pe/institucion/sis/normas-legales/7772769-000002-2026-sis-grep), [anexo RM-CV](https://cdn.www.gob.pe/uploads/document/file/9494985/7772769-criterios-tecnicos-para-el-registro-modular-por-curso-de-vida-rm-cv-en-el-formato-unico-de-atencion-fua.pdf?v=1771946876) | 5, 7, 17 y 24 |

Los umbrales y tablas de los documentos deben implementarse con sus notas y población aplicable. Este informe no propone copiar códigos HIS históricos ni tratar como nacionalmente homologado el catálogo local de ETLSIS.
