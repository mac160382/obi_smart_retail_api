from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies.auth import CurrentUserId
from app.dependencies.database import DatabaseSession
from app.modules.suggested_orders.repository import (
    SuggestedOrderCalculationInProgressError,
)
from app.modules.suggested_orders.schemas import (
    SuggestedOrderCalculationResponse,
    SuggestedOrderItem,
    SuggestedOrderPageResponse,
)
from app.modules.suggested_orders.service import (
    InvalidLocationCodeError,
    SuggestedOrderService,
)

router = APIRouter()


@router.get(
    "",
    response_model=SuggestedOrderPageResponse,
    status_code=status.HTTP_200_OK,
)
def get_suggested_orders(
    _user_id: CurrentUserId,
    db: DatabaseSession,
    location: Annotated[
        int,
        Query(description="Código de la ubicación que se desea consultar"),
    ],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SuggestedOrderPageResponse:
    result = SuggestedOrderService(db).get_by_location(
        location,
        page,
        page_size,
    )
    return SuggestedOrderPageResponse(
        location=result.location,
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
        items=[SuggestedOrderItem.model_validate(item) for item in result.items],
    )


@router.post(
    "/recalculate",
    response_model=SuggestedOrderCalculationResponse,
    status_code=status.HTTP_200_OK,
)
def recalculate_suggested_orders(
    user_id: CurrentUserId,
    db: DatabaseSession,
) -> SuggestedOrderCalculationResponse:
    try:
        result = SuggestedOrderService(db).recalculate(user_id)
    except SuggestedOrderCalculationInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CALCULATION_IN_PROGRESS",
                "message": "El cálculo de pedido sugerido ya está en ejecución.",
            },
        ) from exc
    except InvalidLocationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_LOCATION_CODE",
                "message": (
                    "No fue posible convertir uno o más valores de "
                    "location_code a integer."
                ),
            },
        ) from exc

    return SuggestedOrderCalculationResponse(
        operation="replace",
        destination=result.destination,
        status="completed",
        deleted_rows=result.deleted_rows,
        inserted_rows=result.inserted_rows,
        calculated_at=result.calculated_at,
        duration_ms=result.duration_ms,
    )
