from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.main import app

client = TestClient(app)


def test_assistant_health_is_available_without_authentication() -> None:
    response = client.get("/api/v1/assistant-light/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "disabled"
    assert payload["implemented_tools"] == ["consultar_pedidos_sugeridos"]
    assert payload["real_llm_enabled"] is False


def test_assistant_questions_require_authentication() -> None:
    response = client.get("/api/v1/assistant-light/questions")
    assert response.status_code == 401


def test_assistant_route_requires_authentication() -> None:
    response = client.post(
        "/api/v1/assistant-light/route",
        json={"question": "Consulta pedidos sugeridos"},
    )
    assert response.status_code == 401


def test_assistant_query_requires_authentication() -> None:
    response = client.post(
        "/api/v1/assistant-light/query",
        json={"question": "Consulta pedidos sugeridos"},
    )
    assert response.status_code == 401


def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_user_id] = lambda: UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_authenticated_user_can_preview_routing() -> None:
    authenticated = authenticated_client()
    try:
        response = authenticated.post(
            "/api/v1/assistant-light/route",
            json={"question": "Consulta pedidos sugeridos para la tienda 13"},
        )
    finally:
        clear_overrides()
    assert response.status_code == 200
    assert response.json()["routing"]["tools"] == ["consultar_pedidos_sugeridos"]


def test_authenticated_user_can_list_questions() -> None:
    authenticated = authenticated_client()
    try:
        response = authenticated.get("/api/v1/assistant-light/questions")
    finally:
        clear_overrides()
    assert response.status_code == 200
    payload = response.json()
    assert payload["records_returned"] == 10
    assert sum(1 for row in payload["data"] if row["available"]) == 5


def test_query_reports_disabled_assistant_to_authenticated_user() -> None:
    authenticated = authenticated_client()
    try:
        response = authenticated.post(
            "/api/v1/assistant-light/query",
            json={"question": "Consulta pedidos sugeridos"},
        )
    finally:
        clear_overrides()
    assert response.status_code == 503
    assert "deshabilitado" in response.json()["detail"]


def test_local_restriction_does_not_require_real_llm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "assistant_enabled", True)
    authenticated = authenticated_client()
    try:
        response = authenticated.post(
            "/api/v1/assistant-light/query",
            json={"question": "Recalcula y reemplaza todos los pedidos"},
        )
    finally:
        clear_overrides()
    assert response.status_code == 200
    payload = response.json()
    assert payload["local_restriction"] is True
    assert payload["model_called"] is False
    assert payload["usage"]["total_tokens"] == 0
