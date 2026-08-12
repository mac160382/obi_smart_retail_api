import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db.session import SessionLocal
from app.dependencies.auth import CurrentAuthenticatedUser, CurrentUserId
from app.dependencies.database import DatabaseSession
from app.modules.suggested_orders.events import (
    SSEBroker,
    StoredSSEEvent,
    SuggestedOrderEventRepository,
)
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
logger = logging.getLogger(__name__)


def _load_events_after(event_id: int) -> list[StoredSSEEvent]:
    with SessionLocal() as db:
        return SuggestedOrderEventRepository(db).get_after(
            event_id,
            settings.sse_replay_limit,
        )


def _load_latest_event_id() -> int:
    with SessionLocal() as db:
        return SuggestedOrderEventRepository(db).get_latest_id()


@router.get(
    "/events",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Stream suggested-order recalculation events",
)
async def stream_suggested_order_events(
    request: Request,
    user: CurrentAuthenticatedUser,
    last_event_id: Annotated[
        int | None,
        Header(alias="Last-Event-ID", ge=0),
    ] = None,
) -> StreamingResponse:
    broker: SSEBroker = request.app.state.sse_broker

    async def event_stream() -> AsyncIterator[str]:
        cursor = (
            last_event_id
            if last_event_id is not None
            else await asyncio.to_thread(_load_latest_event_id)
        )

        async def replay_events() -> AsyncIterator[str]:
            nonlocal cursor
            while True:
                replay = await asyncio.to_thread(
                    _load_events_after,
                    cursor,
                )
                if not replay:
                    return
                for event in replay:
                    if event.id > cursor:
                        cursor = event.id
                        yield event.encode()
                if len(replay) < settings.sse_replay_limit:
                    return

        logger.info(
            "Suggested-order SSE client connected",
            extra={"user_id": str(user.user_id), "last_event_id": cursor},
        )
        try:
            async with broker.subscribe() as queue:
                async for encoded_event in replay_events():
                    yield encoded_event

                while True:
                    if await request.is_disconnected():
                        return
                    remaining_seconds = (
                        user.expires_at - datetime.now(UTC)
                    ).total_seconds()
                    if remaining_seconds <= 0:
                        return
                    timeout = min(
                        settings.sse_heartbeat_seconds,
                        remaining_seconds,
                    )
                    try:
                        event = await asyncio.wait_for(
                            queue.get(),
                            timeout=timeout,
                        )
                    except TimeoutError:
                        replayed = False
                        async for encoded_event in replay_events():
                            replayed = True
                            yield encoded_event
                        if not replayed:
                            yield ": keep-alive\n\n"
                        continue

                    if event.id > cursor:
                        cursor = event.id
                        yield event.encode()
        finally:
            logger.info(
                "Suggested-order SSE client disconnected",
                extra={"user_id": str(user.user_id)},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
