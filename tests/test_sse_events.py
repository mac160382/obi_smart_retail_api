import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.dependencies.auth import AuthenticatedUser
from app.main import create_app
from app.modules.suggested_orders import router as suggested_orders_router
from app.modules.suggested_orders.events import SSEBroker, StoredSSEEvent
from app.modules.suggested_orders.router import stream_suggested_order_events


def make_event(event_id: int = 1) -> StoredSSEEvent:
    return StoredSSEEvent(
        id=event_id,
        event_id=uuid4(),
        event_type="suggested-orders.recalculated",
        payload={
            "status": "completed",
            "inserted_rows": 25,
            "forecast_event_id": str(uuid4()),
            "forecast_origin": "2026-08-11",
        },
        created_at=datetime.now(UTC),
    )


def test_stored_event_encodes_sse_contract() -> None:
    event = make_event(17)

    encoded = event.encode()

    assert encoded.startswith("id: 17\n")
    assert "event: suggested-orders.recalculated\n" in encoded
    assert f'"event_id":"{event.event_id}"' in encoded
    assert '"status":"completed"' in encoded
    assert '"forecast_origin":"2026-08-11"' in encoded
    assert encoded.endswith("\n\n")


def test_broker_delivers_event_to_active_subscriber() -> None:
    async def scenario() -> None:
        broker = SSEBroker(queue_size=2)
        event = make_event()
        async with broker.subscribe() as queue:
            await broker.publish(event)
            assert await queue.get() == event

    asyncio.run(scenario())


def test_sse_endpoint_streams_live_event_with_security_headers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        suggested_orders_router,
        "_load_events_after",
        lambda _event_id: [],
    )

    async def scenario() -> None:
        broker = SSEBroker(queue_size=2)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(sse_broker=broker)),
            is_disconnected=AsyncMock(return_value=False),
        )
        user = AuthenticatedUser(
            user_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        response = await stream_suggested_order_events(
            request=request,
            user=user,
            last_event_id=0,
        )
        iterator = response.body_iterator
        next_chunk = asyncio.create_task(anext(iterator))
        await asyncio.sleep(0)
        event = make_event(21)
        await broker.publish(event)

        assert await asyncio.wait_for(next_chunk, timeout=1) == event.encode()
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        await iterator.aclose()

    asyncio.run(scenario())


def test_sse_openapi_requires_oauth2_bearer_authentication() -> None:
    operation = create_app().openapi()["paths"][
        "/api/v1/suggested-orders/events"
    ]["get"]

    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
