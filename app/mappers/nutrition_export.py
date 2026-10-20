"""Legacy review projection; no persistence or export state transitions."""


def legacy_projection(attention):
    context = attention.contexto_clinico
    record = attention.evaluaciones_nutricionales[0]
    row = {
        "Disa": context.get("disa_codigo"),
        "Red": context.get("red_codigo"),
        "MicroRed": context.get("microred_codigo"),
        "Establecimiento": attention.establecimiento_id,
        "IDEESS": context.get("codigo_ideess"),
        "Fecha": attention.fecha_atencion.isoformat(),
        "Hist_Clinica": attention.historia_clinica_snapshot,
        "nDNI": context.get("numero_documento"),
        "TipoDocumento": context.get("tipo_documento_codigo"),
        "SufijoDocumento": context.get("sufijo_documento"),
        "Sexo": context.get("sexo_codigo"),
        "Condicion": context.get("condicion"),
        "Edad": context.get("edad_anios"),
        "Peso": attention.peso_kg,
        "Talla": attention.talla_cm,
        "Hemoglobina": record.hemoglobina,
        "Hbc": record.hemoglobina_corregida,
        "Provincia": context.get("provincia"),
        "Distrito": context.get("distrito"),
        "Localidad": context.get("localidad_codigo_sis"),
        "Altitud": record.altitud_msnm,
        "Enviado": record.enviado,
    }
    if record.tipo == "NINO":
        row.update(
            {
                "Fec_Nacimiento": context.get("fecha_nacimiento"),
                "Edad": (context["edad_anios"] * 12 + context["edad_meses"]),
                "PerimetroAbdominal": attention.perimetro_abdominal_cm,
                "BMI": attention.imc,
                "WHZ": record.whz,
                "HAZ": record.haz,
                "WAZ": record.waz,
                "FechaHemoglobina": record.fecha_hemoglobina,
                "SIS": context.get("sis"),
                **{
                    legacy: getattr(record, field)
                    for legacy, field in (
                        ("JUNTOS", "juntos"),
                        ("PIN", "pin"),
                        ("CRECER", "crecer"),
                        ("Nro_ControlesCred", "nro_controles_cred"),
                        ("Nro_Sachets", "nro_sachets"),
                        ("Nro_Consejerias", "nro_consejerias"),
                        ("Nro_Sesiones", "nro_sesiones"),
                        ("Nro_Visitas", "nro_visitas"),
                        ("InstitucionEducativa", "institucion_educativa"),
                        ("NivelEducativo", "nivel_educativo"),
                        ("Grado", "grado"),
                        ("Turno", "turno"),
                        ("CodigoMatricula", "codigo_matricula"),
                        ("Seccion", "seccion"),
                        ("Aula", "aula"),
                        ("Flag", "flag_legacy"),
                    )
                },
            }
        )
    elif record.tipo == "ADULTO":
        row.update(
            FechaNacimiento=context.get("fecha_nacimiento"),
            PerimetroAbdominal=attention.perimetro_abdominal_cm,
            FechaResultadoHb=record.fecha_hemoglobina,
            SIS=context.get("sis"),
            P65=record.p65,
            VL=record.vl,
            CP=record.cp,
            Pending=record.pending_legacy,
        )
    else:
        row.update(
            Edad_Gestacional=record.edad_gestacional_semanas,
            Hematocrito=record.hematocrito,
            Diagnostico=record.diagnostico,
            PPG=attention.peso_antes_embarazo_kg,
            Tipo_Embarazo=attention.tipo_embarazo_codigo,
            Estado_Ganancia_Peso=record.estado_ganancia_peso,
            FechaHemoglobina=record.fecha_hemoglobina,
            Pending=record.pending_legacy,
        )
    # Keep Decimal precision and date encoding consistent with the API contracts.
    from decimal import Decimal

    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(row, custom_encoder={Decimal: str})
