import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Identity, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import settings
from app.db.base import Base

SUGGESTED_ORDERS_RECALCULATED_EVENT = "suggested-orders.recalculated"


class SuggestedOrderEvent(Base):
    __tablename__ = "suggested_order_events"
    __table_args__ = {"schema": settings.suggested_orders_schema}

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4,
    )
    source_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


@dataclass(frozen=True, slots=True)
class StoredSSEEvent:
    id: int
    event_id: UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    def encode(self) -> str:
        event_data = {
            "event_id": str(self.event_id),
            **self.payload,
        }
        data = json.dumps(
            event_data,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return f"id: {self.id}\nevent: {self.event_type}\ndata: {data}\n\n"


def _to_stored_event(model: SuggestedOrderEvent) -> StoredSSEEvent:
    return StoredSSEEvent(
        id=model.id,
        event_id=model.event_id,
        event_type=model.event_type,
        payload=model.payload,
        created_at=model.created_at,
    )


class SuggestedOrderEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_source_event_id(
        self,
        source_event_id: UUID,
    ) -> StoredSSEEvent | None:
        event = self.db.scalar(
            select(SuggestedOrderEvent).where(
                SuggestedOrderEvent.source_event_id == source_event_id
            )
        )
        return _to_stored_event(event) if event is not None else None

    def create(
        self,
        *,
        event_id: UUID,
        source_event_id: UUID,
        payload: dict[str, Any],
    ) -> StoredSSEEvent:
        event = SuggestedOrderEvent(
            event_id=event_id,
            source_event_id=source_event_id,
            event_type=SUGGESTED_ORDERS_RECALCULATED_EVENT,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return _to_stored_event(event)

    def get_after(
        self,
        event_id: int,
        limit: int,
    ) -> list[StoredSSEEvent]:
        events = self.db.scalars(
            select(SuggestedOrderEvent)
            .where(SuggestedOrderEvent.id > event_id)
            .order_by(SuggestedOrderEvent.id)
            .limit(limit)
        ).all()
        return [_to_stored_event(event) for event in events]

    def get_latest_id(self) -> int:
        return int(
            self.db.scalar(select(func.max(SuggestedOrderEvent.id))) or 0
        )


class SSEBroker:
    def __init__(self, queue_size: int) -> None:
        self.queue_size = queue_size
        self._subscribers: set[asyncio.Queue[StoredSSEEvent]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[StoredSSEEvent]]:
        queue: asyncio.Queue[StoredSSEEvent] = asyncio.Queue(
            maxsize=self.queue_size
        )
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def publish(self, event: StoredSSEEvent) -> None:
        async with self._lock:
            subscribers = tuple(self._subscribers)

        for queue in subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)


def create_sse_broker() -> SSEBroker:
    return SSEBroker(queue_size=settings.sse_client_queue_size)
