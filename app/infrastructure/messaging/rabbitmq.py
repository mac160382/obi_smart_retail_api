import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from aio_pika import DeliveryMode, ExchangeType, Message, connect_robust
from aio_pika.abc import (
    AbstractExchange,
    AbstractRobustChannel,
    AbstractRobustConnection,
)

from app.core.config import settings


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime, Decimal, UUID)):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


@dataclass(frozen=True, slots=True)
class EventMessage:
    event_type: str
    data: dict[str, Any]
    event_version: int = 1
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str | None = None

    def to_json(self) -> bytes:
        payload = {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
            "data": self.data,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8")


class RabbitMQPublisher:
    """Lazy RabbitMQ publisher ready for future application events."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        virtual_host: str,
        exchange_name: str,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.virtual_host = virtual_host
        self.exchange_name = exchange_name
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._exchange: AbstractExchange | None = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return

        self._connection = await connect_robust(
            host=self.host,
            port=self.port,
            login=self.user,
            password=self.password,
            virtualhost=self.virtual_host,
        )
        self._channel = await self._connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )
        self._exchange = await self._channel.declare_exchange(
            self.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def publish(
        self,
        event: EventMessage,
        routing_key: str | None = None,
    ) -> None:
        await self.connect()
        if self._exchange is None:
            raise RuntimeError("RabbitMQ exchange is not available")

        message = Message(
            body=event.to_json(),
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=str(event.event_id),
            correlation_id=event.correlation_id,
            timestamp=event.occurred_at,
            type=event.event_type,
            headers={"event_version": event.event_version},
        )
        await self._exchange.publish(
            message,
            routing_key=routing_key or event.event_type,
            mandatory=True,
        )

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None


def create_rabbitmq_publisher() -> RabbitMQPublisher:
    return RabbitMQPublisher(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        user=settings.rabbitmq_user,
        password=settings.rabbitmq_password,
        virtual_host=settings.rabbitmq_virtual_host,
        exchange_name=settings.rabbitmq_exchange,
    )
