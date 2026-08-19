from datetime import date
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
    def get_forecasts(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/forecasts",
                "source": "public.pronostico",
                "records_returned": 1,
                "total_matching": 1,
                "has_more": False,
            },
            "data": [
                {
                    "item": "A",
                    "location": kwargs.get("location"),
                    "forecast_qty_vendida": 8.5,
                }
            ],
        }

    def get_items(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/items",
                "source": "public.lacteos_maestro_items",
                "records_returned": 1,
            },
            "data": [{"item": kwargs.get("item", "A"), "descripcion": "Leche"}],
        }

    def get_stores(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/stores",
                "source": "public.lacteos_maestro_tiendas",
                "records_returned": 1,
            },
            "data": [{"location": kwargs.get("location", 13), "descripcion": "Centro"}],
        }

    def get_inventory(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/inventory",
                "source": "public.g2_maestro_inventario_lacteos",
                "records_returned": 1,
            },
            "data": [{"item_code": kwargs.get("item_code", "A"), "current_stock_units": 8}],
        }

    def get_promotions(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/promotions",
                "source": "public.g2_lacteos_promociones_vigentes",
                "records_returned": 1,
            },
            "data": [{"item": kwargs.get("item", "A"), "event_code": "PROMO-1"}],
        }

    def get_parameters(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/parameters",
                "source": "public.g2_maestro_inventario_lacteos",
                "records_returned": 1,
            },
            "data": [{"item": kwargs.get("item", "A"), "lead_time_days": 2}],
        }

    def get_executions(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/executions",
                "source": ["phase13_1.txt"],
                "records_returned": 1,
            },
            "data": [{"phase": kwargs.get("phase", "13.1"), "status": "SUCCESS"}],
        }

    def get_model_metrics(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/model/metrics",
                "source": "metrics.csv",
                "records_returned": 1,
            },
            "data": [{"dataset": kwargs.get("dataset", "test"), "mae": "1.5"}],
        }

    def get_shap_global(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/shap/global",
                "source": "shap_global.csv",
                "records_returned": 1,
            },
            "data": [{"predictor": kwargs.get("predictor", "price")}],
        }

    def get_shap_horizons(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/shap/horizons",
                "source": "shap_horizons.csv",
                "records_returned": 1,
            },
            "data": [{"horizon_day": kwargs.get("horizon_day", 1), "predictor": "price"}],
        }

    def get_shap_local(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/shap/local",
                "source": ["shap_sample.csv", "shap_local.csv"],
                "records_returned": 1,
                "local_shap_available": True,
            },
            "data": [{"sample_id": kwargs.get("sample_id", "S1"), "predictor": "price"}],
        }

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

    def get_sales(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "meta": {
                "endpoint": "/api/v1/sales",
                "source": "public.lacteos_ventas_historicas",
                "records_returned": 1,
                "aggregation": kwargs.get("aggregation"),
            },
            "data": [
                {
                    "item": "A",
                    "location": kwargs.get("location"),
                    "qty_vendida": 12,
                }
            ],
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


class FakeForecastResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=8, output_tokens=4, total_tokens=12)
        if len(self.calls) == 1:
            function_call = SimpleNamespace(
                type="function_call",
                name="consultar_pronosticos",
                arguments=(
                    '{"location":13,"forecast_origin":"2026-08-16",'
                    '"target_date_from":"2026-08-17","target_date_to":"2026-08-23"}'
                ),
                call_id="forecast_call_1",
            )
            return SimpleNamespace(
                id="forecast_response_1",
                output=[function_call],
                output_text="",
                usage=usage,
            )
        return SimpleNamespace(
            id="forecast_response_2",
            output=[],
            output_text="Se encontró una muestra de pronósticos.",
            usage=usage,
        )


class FakeForecastOpenAI:
    def __init__(self) -> None:
        self.responses = FakeForecastResponses()


class FakeSalesResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13)
        if len(self.calls) == 1:
            function_call = SimpleNamespace(
                type="function_call",
                name="consultar_ventas",
                arguments=(
                    '{"item":"A","location":13,"date_from":"2026-08-01",'
                    '"date_to":"2026-08-07","aggregation":"week"}'
                ),
                call_id="sales_call_1",
            )
            return SimpleNamespace(
                id="sales_response_1",
                output=[function_call],
                output_text="",
                usage=usage,
            )
        return SimpleNamespace(
            id="sales_response_2",
            output=[],
            output_text="Se encontró una muestra de ventas semanales.",
            usage=usage,
        )


class FakeSalesOpenAI:
    def __init__(self) -> None:
        self.responses = FakeSalesResponses()


def assistant_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "openai_api_key": "",
        "openai_model": "test-model",
        "assistant_real_llm_enabled": False,
        "assistant_enabled_tools": (
            "consultar_pedidos_sugeridos,consultar_pronosticos,consultar_articulos,"
            "consultar_tiendas,consultar_ventas,consultar_inventario,consultar_parametros,"
            "consultar_promociones,consultar_ejecuciones,consultar_metricas_modelo,"
            "consultar_shap_global,consultar_shap_horizontes,consultar_shap_local"
        ),
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


def test_service_reports_an_implemented_but_disabled_tool() -> None:
    settings = assistant_settings(
        assistant_enabled=True,
        app_name="Test API",
        assistant_enabled_tools="consultar_ventas",
    )
    service = AssistantService(MagicMock(), settings, openai_client=FakeOpenAI())
    with pytest.raises(ToolUnavailableError, match="no implementadas o no habilitadas"):
        service.execute(AssistantRequest(question="Consulta las métricas MAE del modelo"))


def test_forecast_function_call_and_final_response_with_simulated_openai() -> None:
    settings = assistant_settings()
    executor = ToolExecutor(FakeRepository(), settings)
    fake_openai = FakeForecastOpenAI()
    client = AssistantClient(settings, executor, openai_client=fake_openai)

    result = client.ask(
        "Consulta pronósticos para la tienda 13.",
        allowed_tools=["consultar_pronosticos"],
    )

    assert result["status"] == "SUCCESS"
    assert result["model_calls"] == 2
    assert result["usage"]["total_tokens"] == 24
    assert result["tools_used"][0]["tool"] == "consultar_pronosticos"
    assert result["tools_used"][0]["arguments"]["forecast_origin"] == date(2026, 8, 16)
    assert "public.pronostico" in result["sources"][0]
    assert fake_openai.responses.calls[0]["tools"][0]["name"] == ("consultar_pronosticos")


def test_service_executes_complete_simulated_forecast_flow() -> None:
    settings = assistant_settings(
        assistant_enabled=True,
        app_name="Test API",
        forecast_schema="public",
        forecast_table="pronostico",
    )
    db = MagicMock()
    db.scalar.return_value = 1
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "item": "A",
            "location": 13,
            "forecast_origin": date(2026, 8, 16),
            "target_date": date(2026, 8, 18),
            "forecast_qty_vendida": 8.5,
        }
    ]
    service = AssistantService(db, settings, openai_client=FakeForecastOpenAI())

    response = service.execute(
        AssistantRequest(question="Consulta los pronósticos para la tienda 13")
    )

    assert response.status == "SUCCESS"
    assert response.selected_tools == ["consultar_pronosticos"]
    assert response.tools_used[0]["tool"] == "consultar_pronosticos"
    assert response.usage.total_tokens == 24
    db.execute.assert_called_once()


def test_sales_function_call_and_final_response_with_simulated_openai() -> None:
    settings = assistant_settings()
    executor = ToolExecutor(FakeRepository(), settings)
    fake_openai = FakeSalesOpenAI()
    client = AssistantClient(settings, executor, openai_client=fake_openai)

    result = client.ask(
        "Consulta las ventas recientes del artículo A en la tienda 13.",
        allowed_tools=["consultar_ventas"],
    )

    assert result["status"] == "SUCCESS"
    assert result["model_calls"] == 2
    assert result["usage"]["total_tokens"] == 26
    assert result["tools_used"][0]["tool"] == "consultar_ventas"
    assert result["tools_used"][0]["arguments"]["date_from"] == date(2026, 8, 1)
    assert result["tools_used"][0]["arguments"]["aggregation"] == "week"
    assert "public.lacteos_ventas_historicas" in result["sources"][0]
    assert fake_openai.responses.calls[0]["tools"][0]["name"] == "consultar_ventas"


def test_service_executes_complete_simulated_sales_flow() -> None:
    settings = assistant_settings(
        assistant_enabled=True,
        app_name="Test API",
        database_schema="public",
        historical_sales_table="lacteos_ventas_historicas",
    )
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item": "A", "location": 13, "qty_vendida": 12}
    ]
    service = AssistantService(db, settings, openai_client=FakeSalesOpenAI())

    response = service.execute(
        AssistantRequest(question="Consulta las ventas recientes del artículo A en la tienda 13")
    )

    assert response.status == "SUCCESS"
    assert response.selected_tools == ["consultar_ventas"]
    assert response.tools_used[0]["tool"] == "consultar_ventas"
    assert response.usage.total_tokens == 26
    db.execute.assert_called_once()
