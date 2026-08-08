import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from sqlalchemy.exc import DataError
from sqlalchemy.orm import Session

from app.core.config import settings
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

    def recalculate(self, user_id: UUID) -> SuggestedOrderCalculationResult:
        started_at = perf_counter()

        try:
            counts = self.repository.replace_suggested_orders()
            self.db.commit()
        except DataError as exc:
            self.db.rollback()
            if getattr(exc.orig, "sqlstate", None) == "22P02":
                raise InvalidLocationCodeError from exc
            raise
        except Exception:
            self.db.rollback()
            raise

        calculated_at = datetime.now(UTC)
        duration_ms = round((perf_counter() - started_at) * 1000)
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
            destination=(
                f"{settings.suggested_orders_schema}."
                f"{settings.suggested_orders_table}"
            ),
            deleted_rows=counts.deleted_rows,
            inserted_rows=counts.inserted_rows,
            calculated_at=calculated_at,
            duration_ms=duration_ms,
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
