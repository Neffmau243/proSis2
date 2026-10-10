"""HTTP endpoints for clinical attention use cases."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthenticatedPrincipal, require_permissions
from app.domain.authorization import Permissions
from app.schemas.attention import (
    AttentionCancellationInput,
    AttentionCreate,
    AttentionResponse,
    NutritionalIndicatorsPreviewInput,
    NutritionalIndicatorsResponse,
)
from app.schemas.nutrition_record import NutritionSendConfirmation
from app.services.attention import AttentionService
from app.services.nutrition_export import NutritionExportService

router = APIRouter(prefix="/atenciones", tags=["Atenciones"])

DatabaseSession = Annotated[Session, Depends(get_db)]
AttentionCreator = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.ATTENTION_CREATE))
]
AttentionReader = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.ATTENTION_READ))
]
AttentionCanceller = Annotated[
    AuthenticatedPrincipal, Depends(require_permissions(Permissions.ATTENTION_CANCEL))
]


@router.post("/{attention_id}/nutricion/exportacion")
def export_nutrition(attention_id: int, principal: AttentionCreator, db: DatabaseSession):
    result = NutritionExportService(db).export_review(
        attention_id, actor_id=principal.user_id, actor_roles=principal.roles,
    )
    return JSONResponse(result, headers={
        "Content-Disposition": f'attachment; filename="nutricion-revision-{attention_id}.json"',
        "Cache-Control": "no-store",
    })


@router.post("/{attention_id}/nutricion/envio", response_model=AttentionResponse)
def confirm_nutrition_sent(
    attention_id: int, payload: NutritionSendConfirmation,
    principal: AttentionCreator, db: DatabaseSession,
):
    return NutritionExportService(db).confirm_sent(
        attention_id, payload, actor_id=principal.user_id, actor_roles=principal.roles,
    )


@router.post("", response_model=AttentionResponse, status_code=status.HTTP_201_CREATED)
def create_attention(
    payload: AttentionCreate,
    principal: AttentionCreator,
    db: DatabaseSession,
) -> AttentionResponse:
    return AttentionService(db).create(
        payload,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )


@router.post(
    "/indicadores-nutricionales/vista-previa",
    response_model=NutritionalIndicatorsResponse,
)
def preview_nutritional_indicators(
    payload: NutritionalIndicatorsPreviewInput,
    principal: AttentionCreator,
    db: DatabaseSession,
) -> NutritionalIndicatorsResponse:
    return AttentionService(db).preview_nutritional_indicators(
        payload,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )


@router.get("/{attention_id}", response_model=AttentionResponse)
def get_attention(
    attention_id: int,
    principal: AttentionReader,
    db: DatabaseSession,
) -> AttentionResponse:
    return AttentionService(db).get(
        attention_id,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )


@router.get("", response_model=list[AttentionResponse])
def list_patient_attentions(
    principal: AttentionReader,
    db: DatabaseSession,
    paciente_id: int = Query(gt=0),
) -> list[AttentionResponse]:
    return AttentionService(db).list_by_patient(
        paciente_id,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )


@router.post("/{attention_id}/anulacion", response_model=AttentionResponse)
def cancel_attention(
    attention_id: int,
    payload: AttentionCancellationInput,
    principal: AttentionCanceller,
    db: DatabaseSession,
) -> AttentionResponse:
    return AttentionService(db).cancel(
        attention_id,
        payload,
        actor_id=principal.user_id,
        actor_roles=principal.roles,
    )
