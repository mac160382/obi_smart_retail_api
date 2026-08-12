import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.suggested_orders.events import (
    StoredSSEEvent,
    SuggestedOrderEventRepository,
)
from app.modules.suggested_orders.repository import SuggestedOrderRepository

logger = logging.getLogger(__name__)


class InvalidLocationCodeError(Exception):
    """Raised when inventory location_code cannot be converted to integer."""


@dataclass(frozen=True)
class SuggestedOrderCalculationResult:
    destination: str
    deleted_rows: int
    inserted_rows: int
    calculated_at: datetime
    duration_ms: int
    notification: StoredSSEEvent | None = None


@dataclass(frozen=True)
class SuggestedOrderPageResult:
    location: int
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[dict[str, object]]


class SuggestedOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SuggestedOrderRepository(db)

    def recalculate(
        self,
        user_id: UUID,
        *,
        source_event_id: UUID | None = None,
        correlation_id: str | None = None,
        forecast_origin: date | None = None,
    ) -> SuggestedOrderCalculationResult:
        started_at = perf_counter()
        event_repository = SuggestedOrderEventRepository(self.db)

        if source_event_id is not None:
            existing = event_repository.find_by_source_event_id(source_event_id)
            if existing is not None:
                payload = existing.payload
                return SuggestedOrderCalculationResult(
                    destination=str(payload["destination"]),
                    deleted_rows=int(payload["deleted_rows"]),
                    inserted_rows=int(payload["inserted_rows"]),
                    calculated_at=datetime.fromisoformat(
                        str(payload["calculated_at"])
                    ),
                    duration_ms=int(payload["duration_ms"]),
                    notification=existing,
                )

        try:
            counts = self.repository.replace_suggested_orders()
            calculated_at = datetime.now(UTC)
            duration_ms = round((perf_counter() - started_at) * 1000)
            destination = (
                f"{settings.suggested_orders_schema}."
                f"{settings.suggested_orders_table}"
            )
            notification = None
            if source_event_id is not None:
                notification = event_repository.create(
                    event_id=uuid4(),
                    source_event_id=source_event_id,
                    payload={
                        "status": "completed",
                        "source_event": "forecast.loaded",
                        "forecast_event_id": str(source_event_id),
                        "forecast_origin": (
                            forecast_origin.isoformat()
                            if forecast_origin is not None
                            else None
                        ),
                        "correlation_id": correlation_id,
                        "destination": destination,
                        "deleted_rows": counts.deleted_rows,
                        "inserted_rows": counts.inserted_rows,
                        "calculated_at": calculated_at.isoformat(),
                        "duration_ms": duration_ms,
                    },
                )
            self.db.commit()
        except DataError as exc:
            self.db.rollback()
            if getattr(exc.orig, "sqlstate", None) == "22P02":
                raise InvalidLocationCodeError from exc
            raise
        except Exception:
            self.db.rollback()
            raise

        logger.info(
            "Suggested orders calculated",
            extra={
                "user_id": str(user_id),
                "deleted_rows": counts.deleted_rows,
                "inserted_rows": counts.inserted_rows,
                "duration_ms": duration_ms,
            },
        )
        return SuggestedOrderCalculationResult(
            destination=destination,
            deleted_rows=counts.deleted_rows,
            inserted_rows=counts.inserted_rows,
            calculated_at=calculated_at,
            duration_ms=duration_ms,
            notification=notification,
        )

    def get_by_location(
        self,
        location: int,
        page: int,
        page_size: int,
    ) -> SuggestedOrderPageResult:
        result = self.repository.get_by_location(location, page, page_size)
        total_pages = (
            (result.total_items + page_size - 1) // page_size
            if result.total_items
            else 0
        )
        return SuggestedOrderPageResult(
            location=location,
            page=page,
            page_size=page_size,
            total_items=result.total_items,
            total_pages=total_pages,
            items=result.items,
        )
