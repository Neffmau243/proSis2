from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.mappers.attention import attention_to_response


def test_attention_mapper_exposes_history_display_data_from_real_relations() -> None:
    entity = SimpleNamespace(
        fua_impresion=None,
        id=1,
        paciente_id=10,
        establecimiento_id=2,
        profesional_id=3,
        especialidad_codigo="MEDICINA_GENERAL",
        consultorio_id=4,
        consultorio=SimpleNamespace(nombre="Consultorio de medicina"),
        modalidad_atencion_codigo="AMBULATORIA",
        grupo_etario_codigo="ADULTO",
        grupo_atencion_codigo="GESTANTES",
        fecha_atencion=datetime(2026, 9, 10, 9, 30),
        fecha_atendido=None,
        historia_clinica_snapshot="HC-001",
        edad_anios=36,
        paciente=SimpleNamespace(fecha_nacimiento=date(1990, 5, 10)),
        peso_kg=Decimal("72.50"),
        talla_cm=Decimal("170.00"),
        perimetro_abdominal_cm=None,
        tipo_embarazo_codigo="MULTIPLE",
        peso_antes_embarazo_kg=Decimal("58.40"),
        fecha_probable_parto=date(2027, 3, 15),
        fecha_parto=None,
        presion_sistolica=120,
        presion_diastolica=80,
        temperatura_c=Decimal("36.5"),
        imc=Decimal("25.087"),
        pe=None,
        te=None,
        pt=None,
        referencia_nutricional=None,
        hora_inicio=None,
        hora_fin=None,
        admision=None,
        observaciones=None,
        estado="ATENDIDO",
        created_by_usuario_id=7,
        created_at=datetime(2026, 9, 10, 9, 30),
        updated_at=datetime(2026, 9, 10, 9, 30),
        prestaciones=[],
        diagnosticos=[],
    )

    result = attention_to_response(entity)  # type: ignore[arg-type]

    assert result.consultorio_nombre == "Consultorio de medicina"
    assert result.edad_detallada == "36 años, 4 meses y 0 días"
    assert result.grupo_atencion_codigo == "GESTANTES"
    assert result.peso_antes_embarazo_kg == Decimal("58.40")
    assert result.tipo_embarazo_codigo == "MULTIPLE"
    assert result.fecha_probable_parto == date(2027, 3, 15)
    assert result.fecha_parto is None

    # Renaming or moving today's catalog cannot rewrite the stored encounter.
    entity.contexto_clinico = {
        "consultorio_nombre": "Sala original",
        "consultorio_ruta": "Medicina / Sala original",
        "especialidad_nombre": "Pediatría",
        "establecimiento_nombre": "Sede original",
        "edad_detallada": result.edad_detallada,
    }
    entity.consultorio.nombre = "Nombre actual distinto"
    historical = attention_to_response(entity)
    assert historical.consultorio_nombre == "Sala original"
    assert historical.consultorio_ruta == "Medicina / Sala original"
    assert historical.especialidad_nombre == "Pediatría"
    assert historical.establecimiento_nombre == "Sede original"
