import asyncio
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from aio_pika import DeliveryMode

from app.infrastructure.messaging import forecast_consumer as consumer_module
from app.infrastructure.messaging.forecast_consumer import (
    FORECAST_LOADED_EVENT,
    RabbitMQForecastLoadedConsumer,
)
from app.modules.suggested_orders.repository import (
    SuggestedOrderCalculationInProgressError,
)


def make_consumer() -> RabbitMQForecastLoadedConsumer:
    broker = MagicMock()
    broker.publish = AsyncMock()
    return RabbitMQForecastLoadedConsumer(
        host="rabbitmq",
        port=5672,
        user="smartretail",
        password="test-password",
        virtual_host="smart_retail",
        exchange_name="smart_retail.events",
        queue_name="smart_retail.forecast.loaded",
        routing_key="forecast.loaded",
        sse_broker=broker,
    )


def make_message() -> MagicMock:
    event_id = uuid4()
    message = MagicMock()
    message.body = json.dumps(
        {
            "event_id": str(event_id),
            "event_type": FORECAST_LOADED_EVENT,
            "event_version": 1,
            "occurred_at": "2026-08-11T12:00:00+00:00",
            "correlation_id": "forecast-import-123",
            "data": {"forecast_origin": "2026-08-11"},
        }
    ).encode()
    message.delivery_mode = DeliveryMode.PERSISTENT
    message.type = FORECAST_LOADED_EVENT
    message.message_id = str(event_id)
    message.redelivered = False
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    message.reject = AsyncMock()
    return message


def test_consumer_declares_durable_queue_and_manual_ack(
    monkeypatch,
) -> None:
    exchange = MagicMock()
    queue = MagicMock()
    queue.bind = AsyncMock()
    queue.consume = AsyncMock(return_value="consumer-tag")
    channel = MagicMock()
    channel.set_qos = AsyncMock()
    channel.declare_exchange = AsyncMock(return_value=exchange)
    channel.declare_queue = AsyncMock(return_value=queue)
    connection = MagicMock()
    connection.is_closed = False
    connection.channel = AsyncMock(return_value=channel)
    connect_robust = AsyncMock(return_value=connection)
    monkeypatch.setattr(consumer_module, "connect_robust", connect_robust)
    consumer = make_consumer()

    asyncio.run(consumer.connect())

    channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    channel.declare_queue.assert_awaited_once_with(
        "smart_retail.forecast.loaded",
        durable=True,
    )
    queue.bind.assert_awaited_once_with(exchange, routing_key="forecast.loaded")
    queue.consume.assert_awaited_once_with(
        consumer._handle_message,
        no_ack=False,
    )


def test_consumer_acknowledges_only_after_success() -> None:
    consumer = make_consumer()
    notification = MagicMock()
    consumer._recalculate = MagicMock(
        return_value=SimpleNamespace(notification=notification)
    )
    message = make_message()

    asyncio.run(consumer._handle_message(message))

    consumer._recalculate.assert_called_once()
    assert consumer._recalculate.call_args.args[0].forecast_origin == date(
        2026,
        8,
        11,
    )
    consumer.sse_broker.publish.assert_awaited_once_with(notification)
    message.ack.assert_awaited_once_with()
    message.nack.assert_not_awaited()
    message.reject.assert_not_awaited()


def test_consumer_rejects_invalid_or_non_persistent_event() -> None:
    consumer = make_consumer()
    consumer._recalculate = MagicMock()
    message = make_message()
    message.delivery_mode = DeliveryMode.NOT_PERSISTENT

    asyncio.run(consumer._handle_message(message))

    consumer._recalculate.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


def test_consumer_rejects_event_without_forecast_origin() -> None:
    consumer = make_consumer()
    consumer._recalculate = MagicMock()
    message = make_message()
    payload = json.loads(message.body)
    payload["data"] = {}
    message.body = json.dumps(payload).encode()

    asyncio.run(consumer._handle_message(message))

    consumer._recalculate.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


def test_consumer_requeues_event_when_calculation_is_busy() -> None:
    consumer = make_consumer()
    consumer._recalculate = MagicMock(
        side_effect=SuggestedOrderCalculationInProgressError
    )
    message = make_message()

    asyncio.run(consumer._handle_message(message))

    message.nack.assert_awaited_once_with(requeue=True)
    message.ack.assert_not_awaited()
