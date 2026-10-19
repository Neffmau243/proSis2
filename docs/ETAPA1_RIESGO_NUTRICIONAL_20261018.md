# Primera etapa: valoración y seguimiento nutricional

Implementación del 17–18 de octubre de 2026. Fuentes y contraste normativo: [revisión MINSA, EsSalud y SIS](GRUPOS_RIESGO_MINSA_ESSALUD_FUA_20261017.md).

## Funcionamiento

1. Al ingresar peso, talla y fecha, el servidor calcula la valoración aplicable a la edad. La vista previa no asigna riesgos.
2. Al guardar la atención se conserva una copia de los resultados, su referencia, la versión local del cálculo y las sugerencias. No se recalculan atenciones anteriores.
3. «Confirmar seguimiento» abre el grupo, la fecha y el motivo sugeridos. El profesional revisa el motivo y puede registrar un próximo control.
4. Se guarda la atención de origen, la evaluación original y el usuario que confirma. El cliente no puede enviar una evaluación de origen fabricada.
5. Un control posterior normal no cierra automáticamente el periodo. El cierre exige un motivo en las categorías nuevas. La fecha de fin es inclusiva.

También se puede registrar una valoración profesional sin sugerencia automática, tanto en el registro del paciente como posteriormente. Las categorías nuevas requieren motivo. El próximo control no puede ser anterior al inicio; se conservan las restricciones contra periodos superpuestos.

## Valoración por edad

- Menores de 5 años: P/E, T/E y P/T sobre referencia OMS 2006; clasificaciones revisadas con las tablas MINSA consultadas. Talla alta desde Z > +2; P/E > +2 se presenta como sobrepeso; P/T entre +1 y +2 se presenta normal, sin convertir una medición aislada en riesgo confirmado.
- Desde los 5 años: IMC/edad y T/E. En el mes calendario 60 se usa la referencia mensual OMS 2006 instalada; desde 61 meses, OMS 2007 por meses completos. No se extrapolan tablas ni se muestran P/E y P/T como indicadores principales de escolares.
- La transición general al IMC adulto se realiza a los 19 años cumplidos. Se muestran los grados de delgadez y obesidad; a partir de 60 años se mantienen los umbrales diferenciados del adulto mayor.
- Los grupos maternos conservan su valoración pregestacional y sus etiquetas sin grados. No se generan sugerencias generales a partir del IMC actual de una gestante o puérpera.

`MINSA-2026.1` es el identificador **local** del perfil de cálculo de esta implementación, no un código oficial emitido por MINSA ni una declaración de homologación del sistema.

## Evolución infantil

La comparación implementada es descriptiva y se limita a menores de 5 años. Busca el control anterior con peso y talla positivos, atendido y visible para el usuario. Excluye atenciones anuladas, futuras, del mismo día o anteriores al nacimiento. Informa fecha, intervalo y diferencias de peso/talla.

Cuando el peso o la talla no aumentan, sugiere revisar la evolución y la técnica de medición. No diagnostica desnutrición ni aplica una curva de velocidad de crecimiento. Sin mediciones suficientes, informa «datos insuficientes», nunca «crecimiento normal».

## Catálogo y trazabilidad

Categorías locales incorporadas, separadas del legado ETLSIS:

| Código local | Uso |
| --- | --- |
| `NUT_HALLAZGO` | Seguimiento de un hallazgo antropométrico, con confirmación. |
| `NUT_CRECIMIENTO` | Revisión de la evolución del crecimiento infantil. |
| `NUT_RIESGO_EVALUADO` | Riesgo nutricional valorado por el profesional. |

Se conservan los cuatro códigos antiguos, sus nombres y sus periodos. No se homologan ni convierten masivamente en diagnósticos actuales. La ficha muestra próximo control, origen y motivo de cierre. «Sin seguimiento vigente registrado» describe el registro administrativo, no ausencia de riesgo clínico.

La migración `20261017_0037_nutrition_followup` agrega columnas opcionales, relaciones y las tres categorías. La aplicación local pasó de la revisión 0036 a 0037 verificando igualdad de las huellas de las 29 atenciones existentes —valoración y copia FUA— y del periodo de riesgo anterior. Registro de comprobación: `tmp/riesgos-etapa1-20261017/migracion-local.json`.

## Límites de esta etapa

No implementa formularios o puntajes MST, MUST o MNA-SF: el tamizaje estructurado figura como **no evaluado**. Tampoco calcula riesgo cardiometabólico por perímetro abdominal, HVB ni otros dominios. No asigna CIE-10 ni prestaciones por una alerta. La integración oficial al FUA corresponde a la siguiente etapa; las copias históricas se conservan.

## Verificaciones

- 436 pruebas unitarias del backend aprobadas.
- 28 pruebas de integración HTTP/MySQL aprobadas en una base nueva y desechable, incluida confirmación, cierre, origen inmutable, falta de motivo, intento de enviar evaluación fabricada, atención de otro paciente, ausencia de sugerencia, selección del control infantil anterior y descarte de medidas históricas inválidas. Registro de la ejecución final: `tmp/riesgos-etapa1-20261017/mysql-final.log`.
- 77 pruebas del frontend aprobadas para resultados, sugerencias, primera apertura del diálogo, presentación histórica, servicios y compatibilidad con registro/resumen de pacientes. Compilación y comprobación de tipos aprobadas.
- Ruff en los módulos principales modificados; detector estático de interfaz sin incidencias.
- Formulario comprobado a 1280 × 900 y 390 × 844.
- Paciente ficticio #21: atención #30 guardada con 50 kg, 175 cm e IMC 16.327, «Delgadez grado II». Antes de confirmar no tenía seguimiento. Se confirmó con motivo explícito de prueba y próximo control 2026-10-31; permaneció registrado tras recargar. El control anterior conserva su etiqueta «Bajo peso». Se comprobó también la edición y que «Agregar riesgo» abra un periodo nuevo después de editar uno anterior.

Capturas de la prueba en `tmp/riesgos-etapa1-20261017/`. Los datos de este recorrido son ficticios.
