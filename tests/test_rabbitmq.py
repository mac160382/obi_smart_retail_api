import asyncio
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from aio_pika import DeliveryMode

from app.infrastructure.messaging import rabbitmq as rabbitmq_module
from app.infrastructure.messaging.rabbitmq import EventMessage, RabbitMQPublisher


def make_publisher() -> RabbitMQPublisher:
    return RabbitMQPublisher(
        host="rabbitmq",
        port=5672,
        user="smartretail",
        password="test-password",
        virtual_host="smart_retail",
        exchange_name="smart_retail.events",
    )


def test_event_message_serializes_metadata_and_business_data() -> None:
    event = EventMessage(
        event_type="forecast.imported",
        event_version=2,
        correlation_id="request-123",
        data={
            "business_date": date(2026, 8, 10),
            "quantity": Decimal("12.50"),
        },
    )

    payload = json.loads(event.to_json())

    assert UUID(payload["event_id"]) == event.event_id
    assert payload["event_type"] == "forecast.imported"
    assert payload["event_version"] == 2
    assert payload["correlation_id"] == "request-123"
    assert payload["data"] == {
        "business_date": "2026-08-10",
        "quantity": "12.50",
    }


def test_publisher_declares_durable_exchange_and_publishes_persistent_message(
    monkeypatch,
) -> None:
    exchange = MagicMock()
    exchange.publish = AsyncMock()
    channel = MagicMock()
    channel.declare_exchange = AsyncMock(return_value=exchange)
    connection = MagicMock()
    connection.is_closed = False
    connection.channel = AsyncMock(return_value=channel)
    connect_robust = AsyncMock(return_value=connection)
    monkeypatch.setattr(rabbitmq_module, "connect_robust", connect_robust)
    publisher = make_publisher()
    event = EventMessage(
        event_type="suggested_orders.recalculated",
        occurred_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        data={"inserted_rows": 25},
    )

    asyncio.run(publisher.publish(event))

    connect_robust.assert_awaited_once_with(
        host="rabbitmq",
        port=5672,
        login="smartretail",
        password="test-password",
        virtualhost="smart_retail",
    )
    connection.channel.assert_awaited_once_with(
        publisher_confirms=True,
        on_return_raises=True,
    )
    channel.declare_exchange.assert_awaited_once()
    message = exchange.publish.await_args.args[0]
    assert message.delivery_mode == DeliveryMode.PERSISTENT
    assert message.message_id == str(event.event_id)
    assert exchange.publish.await_args.kwargs == {
        "routing_key": "suggested_orders.recalculated",
        "mandatory": True,
    }
