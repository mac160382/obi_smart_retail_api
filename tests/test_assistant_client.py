from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.modules.assistant.client import AssistantClient, AssistantUnavailableError
from app.modules.assistant.schemas import AssistantRequest
from app.modules.assistant.service import AssistantService, ToolUnavailableError
from app.modules.assistant.tool_executor import ToolExecutor


class FakeRepository:
    def get_suggested_orders(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/suggested-orders",
                "source": "public.pedido_sugerido",
                "records_returned": 1,
                "total_matching": 1,
                "has_more": False,
            },
            "data": [{"item": "A", "location": kwargs.get("location"), "sugerido": 4}],
        }


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)
        if len(self.calls) == 1:
            function_call = SimpleNamespace(
                type="function_call",
                name="consultar_pedidos_sugeridos",
                arguments='{"location":13,"limit":5}',
                call_id="call_1",
            )
            return SimpleNamespace(
                id="response_1",
                output=[function_call],
                output_text="",
                usage=usage,
            )
        return SimpleNamespace(
            id="response_2",
            output=[],
            output_text="Se encontró una muestra de pedidos sugeridos.",
            usage=usage,
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def assistant_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "openai_api_key": "",
        "openai_model": "test-model",
        "assistant_real_llm_enabled": False,
        "assistant_enabled_tools": "consultar_pedidos_sugeridos",
        "assistant_max_records": 25,
        "assistant_max_model_calls": 4,
        "assistant_max_tool_calls": 6,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_function_call_and_final_response_with_simulated_openai() -> None:
    settings = assistant_settings()
    executor = ToolExecutor(FakeRepository(), settings)
    fake_openai = FakeOpenAI()
    client = AssistantClient(settings, executor, openai_client=fake_openai)

    result = client.ask(
        "Consulta pedidos sugeridos para la tienda 13.",
        allowed_tools=["consultar_pedidos_sugeridos"],
    )

    assert result["status"] == "SUCCESS"
    assert result["model_calls"] == 2
    assert result["usage"]["total_tokens"] == 30
    assert result["tools_used"][0]["tool"] == "consultar_pedidos_sugeridos"
    assert "Fuentes utilizadas:" in result["answer"]
    assert fake_openai.responses.calls[0]["tool_choice"] == "required"
    assert fake_openai.responses.calls[0]["parallel_tool_calls"] is False
    assert fake_openai.responses.calls[0]["store"] is False
    assert fake_openai.responses.calls[1]["store"] is False


def test_real_llm_is_disabled_by_default() -> None:
    settings = assistant_settings()
    client = AssistantClient(settings, ToolExecutor(FakeRepository(), settings))
    with pytest.raises(AssistantUnavailableError, match="deshabilitado"):
        client.ask("Consulta pedidos", allowed_tools=["consultar_pedidos_sugeridos"])


def test_local_restriction_has_no_model_usage() -> None:
    settings = assistant_settings()
    client = AssistantClient(settings, ToolExecutor(FakeRepository(), settings))
    result = client.local_restriction("Recalcula los pedidos")
    assert result["model_called"] is False
    assert result["usage"]["total_tokens"] == 0
    assert result["local_restriction"] is True


def test_service_executes_complete_simulated_flow() -> None:
    settings = assistant_settings(
        assistant_enabled=True,
        app_name="Test API",
        suggested_orders_schema="public",
        suggested_orders_table="pedido_sugerido",
    )
    db = MagicMock()
    db.scalar.return_value = 1
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item": "A", "location": 13, "sugerido": 4}
    ]
    service = AssistantService(db, settings, openai_client=FakeOpenAI())

    response = service.execute(
        AssistantRequest(question="Consulta pedidos sugeridos para la tienda 13")
    )

    assert response.status == "SUCCESS"
    assert response.model_called is True
    assert response.model_calls == 2
    assert response.selected_tools == ["consultar_pedidos_sugeridos"]
    assert response.tools_used[0]["tool"] == "consultar_pedidos_sugeridos"
    db.execute.assert_called_once()


def test_service_reports_a_planned_but_unimplemented_tool() -> None:
    settings = assistant_settings(
        assistant_enabled=True,
        assistant_enabled_tools="consultar_pedidos_sugeridos,consultar_pronosticos",
        app_name="Test API",
    )
    service = AssistantService(MagicMock(), settings, openai_client=FakeOpenAI())
    with pytest.raises(ToolUnavailableError, match="pendientes de migración"):
        service.execute(AssistantRequest(question="Consulta los pronósticos"))
