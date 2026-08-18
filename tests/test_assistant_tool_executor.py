from datetime import date
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.assistant.tool_executor import ToolExecutor


class FakeRepository:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    def get_forecasts(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": "public.pronostico",
                "records_returned": 1,
                "total_matching": 1,
                "has_more": False,
            },
            "data": [{"item": "A", "location": 13, "forecast_qty_vendida": 8.5}],
        }

    def get_sales(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": "public.lacteos_ventas_historicas",
                "records_returned": 1,
            },
            "data": [{"item": "A", "location": 13, "qty_vendida": 12}],
        }

    def get_suggested_orders(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": "public.pedido_sugerido",
                "records_returned": 1,
                "total_matching": 1,
                "has_more": False,
            },
            "data": [{"item": "A", "location": 13, "sugerido": 4}],
        }


def assistant_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "assistant_enabled_tools": (
            "consultar_pedidos_sugeridos,consultar_pronosticos,consultar_ventas"
        ),
        "assistant_max_records": 25,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_executor_normalizes_limits_dates_and_defaults() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=10))
    payload, trace = executor.execute(
        "consultar_pedidos_sugeridos",
        {
            "location": "13",
            "forecast_origin": "2026-08-16",
            "order_type": "positive",
            "limit": 99,
        },
    )
    assert repository.arguments["forecast_origin"] == date(2026, 8, 16)
    assert repository.arguments["location"] == 13
    assert repository.arguments["status"] == "Estimado"
    assert repository.arguments["limit"] == 10
    assert trace.records_returned == 1
    assert payload["data"][0]["sugerido"] == 4


def test_executor_rejects_unknown_arguments() -> None:
    executor = ToolExecutor(FakeRepository(), assistant_settings())
    with pytest.raises(ValueError, match="no permitidos"):
        executor.execute(
            "consultar_pedidos_sugeridos",
            {"sql": "DELETE FROM pedido_sugerido"},
        )


def test_executor_rejects_disabled_tool() -> None:
    executor = ToolExecutor(
        FakeRepository(),
        assistant_settings(assistant_enabled_tools=""),
    )
    with pytest.raises(ValueError, match="no habilitada"):
        executor.execute("consultar_pedidos_sugeridos", {})


def test_executor_normalizes_forecast_filters() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=8))
    payload, trace = executor.execute(
        "consultar_pronosticos",
        {
            "item_code": "101",
            "location": "13",
            "forecast_origin": "2026-08-16",
            "target_date_from": "2026-08-17",
            "target_date_to": "2026-08-23",
            "horizon_day": 3,
            "limit": 50,
        },
    )
    assert repository.arguments["item_code"] == 101
    assert repository.arguments["location"] == 13
    assert repository.arguments["forecast_origin"] == date(2026, 8, 16)
    assert repository.arguments["target_date_from"] == date(2026, 8, 17)
    assert repository.arguments["target_date_to"] == date(2026, 8, 23)
    assert repository.arguments["limit"] == 8
    assert "order_type" not in repository.arguments
    assert trace.tool == "consultar_pronosticos"
    assert payload["data"][0]["forecast_qty_vendida"] == 8.5


def test_executor_rejects_inverted_forecast_date_range() -> None:
    executor = ToolExecutor(FakeRepository(), assistant_settings())
    with pytest.raises(ValueError, match="no puede ser posterior"):
        executor.execute(
            "consultar_pronosticos",
            {
                "target_date_from": "2026-08-23",
                "target_date_to": "2026-08-17",
            },
        )


def test_executor_normalizes_sales_filters_and_defaults() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=6))
    payload, trace = executor.execute(
        "consultar_ventas",
        {
            "item": "A",
            "location": "13",
            "date_from": "2026-08-01",
            "date_to": "2026-08-07",
            "aggregation": "week",
            "limit": 50,
        },
    )
    assert repository.arguments == {
        "item": "A",
        "location": 13,
        "date_from": date(2026, 8, 1),
        "date_to": date(2026, 8, 7),
        "aggregation": "week",
        "limit": 6,
    }
    assert trace.tool == "consultar_ventas"
    assert payload["data"][0]["qty_vendida"] == 12


def test_executor_rejects_invalid_sales_aggregation() -> None:
    executor = ToolExecutor(FakeRepository(), assistant_settings())
    with pytest.raises(ValueError, match="aggregation debe ser"):
        executor.execute("consultar_ventas", {"aggregation": "month"})


def test_executor_rejects_inverted_sales_date_range() -> None:
    executor = ToolExecutor(FakeRepository(), assistant_settings())
    with pytest.raises(ValueError, match="date_from no puede"):
        executor.execute(
            "consultar_ventas",
            {"date_from": "2026-08-08", "date_to": "2026-08-01"},
        )
