import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from aio_pika import DeliveryMode, ExchangeType, connect_robust
from aio_pika.abc import (
    AbstractIncomingMessage,
    AbstractRobustChannel,
    AbstractRobustConnection,
    AbstractRobustQueue,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.suggested_orders.repository import (
    SuggestedOrderCalculationInProgressError,
)
from app.modules.suggested_orders.service import (
    InvalidLocationCodeError,
    SuggestedOrderService,
)

logger = logging.getLogger(__name__)

FORECAST_LOADED_EVENT = "forecast.loaded"


class InvalidForecastLoadedEventError(ValueError):
    """Raised when an incoming forecast.loaded event breaks its contract."""


@dataclass(frozen=True, slots=True)
class ForecastLoadedEvent:
    event_id: UUID
    correlation_id: str | None
    data: dict[str, Any]

    @classmethod
    def from_message(
        cls,
        message: AbstractIncomingMessage,
    ) -> "ForecastLoadedEvent":
        if message.delivery_mode != DeliveryMode.PERSISTENT:
            raise InvalidForecastLoadedEventError(
                "forecast.loaded must be a persistent message"
            )

        try:
            payload = json.loads(message.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidForecastLoadedEventError(
                "forecast.loaded body must be valid UTF-8 JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidForecastLoadedEventError(
                "forecast.loaded body must be a JSON object"
            )
        if payload.get("event_type") != FORECAST_LOADED_EVENT:
            raise InvalidForecastLoadedEventError(
                "event_type must be forecast.loaded"
            )
        if payload.get("event_version") != 1:
            raise InvalidForecastLoadedEventError(
                "event_version must be 1"
            )
        if message.type not in (None, FORECAST_LOADED_EVENT):
            raise InvalidForecastLoadedEventError(
                "AMQP message type must be forecast.loaded"
            )

        try:
            event_id = UUID(str(payload["event_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidForecastLoadedEventError(
                "event_id must be a valid UUID"
            ) from exc

        if message.message_id not in (None, str(event_id)):
            raise InvalidForecastLoadedEventError(
                "AMQP message_id must match event_id"
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise InvalidForecastLoadedEventError(
                "data must be a JSON object"
            )

        correlation_id = payload.get("correlation_id")
        if correlation_id is not None and not isinstance(correlation_id, str):
            raise InvalidForecastLoadedEventError(
                "correlation_id must be a string or null"
            )

        return cls(
            event_id=event_id,
            correlation_id=correlation_id,
            data=data,
        )


class RabbitMQForecastLoadedConsumer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        virtual_host: str,
        exchange_name: str,
        queue_name: str,
        routing_key: str,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.virtual_host = virtual_host
        self.exchange_name = exchange_name
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.session_factory = session_factory
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._queue: AbstractRobustQueue | None = None
        self._consumer_tag: str | None = None

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
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        exchange = await self._channel.declare_exchange(
            self.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(
            self.queue_name,
            durable=True,
        )
        await self._queue.bind(exchange, routing_key=self.routing_key)
        self._consumer_tag = await self._queue.consume(
            self._handle_message,
            no_ack=False,
        )

    def _recalculate(self, event: ForecastLoadedEvent) -> None:
        with self.session_factory() as db:
            result = SuggestedOrderService(db).recalculate(event.event_id)
        logger.info(
            "forecast.loaded processed",
            extra={
                "event_id": str(event.event_id),
                "correlation_id": event.correlation_id,
                "inserted_rows": result.inserted_rows,
                "deleted_rows": result.deleted_rows,
                "duration_ms": result.duration_ms,
            },
        )

    async def _handle_message(
        self,
        message: AbstractIncomingMessage,
    ) -> None:
        try:
            event = ForecastLoadedEvent.from_message(message)
        except InvalidForecastLoadedEventError:
            logger.exception(
                "Invalid forecast.loaded event rejected",
                extra={"message_id": message.message_id},
            )
            await message.reject(requeue=False)
            return

        try:
            await asyncio.to_thread(self._recalculate, event)
        except SuggestedOrderCalculationInProgressError:
            logger.warning(
                "Suggested-order calculation is already in progress",
                extra={"event_id": str(event.event_id)},
            )
            await message.nack(requeue=True)
            return
        except InvalidLocationCodeError:
            logger.exception(
                "forecast.loaded cannot be processed due to invalid inventory data",
                extra={"event_id": str(event.event_id)},
            )
            await message.reject(requeue=False)
            return
        except Exception:
            logger.exception(
                "Unexpected error processing forecast.loaded",
                extra={"event_id": str(event.event_id)},
            )
            await message.nack(requeue=not message.redelivered)
            return

        await message.ack()

    async def close(self) -> None:
        if self._queue is not None and self._consumer_tag is not None:
            await self._queue.cancel(self._consumer_tag)
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._queue = None
        self._consumer_tag = None


def create_forecast_loaded_consumer() -> RabbitMQForecastLoadedConsumer:
    return RabbitMQForecastLoadedConsumer(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        user=settings.rabbitmq_user,
        password=settings.rabbitmq_password,
        virtual_host=settings.rabbitmq_virtual_host,
        exchange_name=settings.rabbitmq_exchange,
        queue_name=settings.rabbitmq_forecast_loaded_queue,
        routing_key=settings.rabbitmq_forecast_loaded_routing_key,
    )
