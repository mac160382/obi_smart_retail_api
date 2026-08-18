from datetime import date
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.assistant.tool_executor import ToolExecutor


class FakeRepository:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

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
        "assistant_enabled_tools": "consultar_pedidos_sugeridos",
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
