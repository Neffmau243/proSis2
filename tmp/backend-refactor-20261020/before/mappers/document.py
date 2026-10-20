from app.models.documents import Certificate, Fua, Referral
from app.schemas.document import CertificateResponse, FuaResponse, ReferralResponse


def fua_to_response(entity: Fua) -> FuaResponse:
    return FuaResponse.model_validate(entity)


def certificate_to_response(entity: Certificate) -> CertificateResponse:
    return CertificateResponse(
        id=entity.id,
        atencion_id=entity.atencion_id,
        establecimiento_id=entity.establecimiento_id,
        profesional_id=entity.profesional_id,
        numero_certificado=entity.numero_certificado,
        tipo=entity.tipo,
        fecha_emision=entity.fecha_emision,
        consultorio=entity.consultorio,
        admision=entity.admision,
        estado=entity.estado,
        prestaciones=[item.prestacion_codigo for item in entity.prestaciones],
    )


def referral_to_response(entity: Referral) -> ReferralResponse:
    return ReferralResponse.model_validate(entity)
