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

    def get_items(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "public.lacteos_maestro_items", "records_returned": 1},
            "data": [{"item": "A", "descripcion": "Leche"}],
        }

    def get_stores(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "public.lacteos_maestro_tiendas", "records_returned": 1},
            "data": [{"location": 13, "descripcion": "Centro"}],
        }

    def get_inventory(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": "public.g2_maestro_inventario_lacteos",
                "records_returned": 1,
            },
            "data": [{"item_code": "A", "location_code": "13"}],
        }

    def get_promotions(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": "public.g2_lacteos_promociones_vigentes",
                "records_returned": 1,
            },
            "data": [{"item": "A", "event_code": "PROMO-1"}],
        }

    def get_parameters(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "public.g2_maestro_inventario_lacteos", "records_returned": 1},
            "data": [{"item": "A", "lead_time_days": 2}],
        }

    def get_executions(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": ["phase13_1.txt"], "records_returned": 1},
            "data": [{"phase": kwargs.get("phase"), "status": "SUCCESS"}],
        }

    def get_model_metrics(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "metrics.csv", "records_returned": 1},
            "data": [{"evaluation_level": "period", "mae": "1.5"}],
        }

    def get_shap_global(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "shap_global.csv", "records_returned": 1},
            "data": [{"predictor": "price"}],
        }

    def get_shap_horizons(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {"source": "shap_horizons.csv", "records_returned": 1},
            "data": [{"horizon_day": kwargs.get("horizon_day"), "predictor": "price"}],
        }

    def get_shap_local(self, **kwargs: Any) -> dict[str, Any]:
        self.arguments = kwargs
        return {
            "meta": {
                "source": ["shap_sample.csv", "shap_local.csv"],
                "records_returned": 1,
                "local_shap_available": True,
            },
            "data": [{"sample_id": kwargs.get("sample_id"), "predictor": "price"}],
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
            "consultar_pedidos_sugeridos,consultar_pronosticos,consultar_articulos,"
            "consultar_tiendas,consultar_ventas,consultar_inventario,consultar_parametros,"
            "consultar_promociones,consultar_ejecuciones,consultar_metricas_modelo,"
            "consultar_shap_global,consultar_shap_horizontes,consultar_shap_local"
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


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            "consultar_articulos",
            {"item": "A", "itemtype": "1", "familia_cod": "10"},
            {"item": "A", "itemtype": 1, "familia_cod": 10, "limit": 7},
        ),
        (
            "consultar_tiendas",
            {"location": "13", "region": "Norte", "estado": "1"},
            {"location": 13, "region": "Norte", "estado": 1, "limit": 7},
        ),
        (
            "consultar_inventario",
            {"item_code": "A", "location_code": "13", "proveedor_code": "P1"},
            {
                "item_code": "A",
                "location_code": "13",
                "proveedor_code": "P1",
                "limit": 7,
            },
        ),
        (
            "consultar_promociones",
            {"item": "A", "active_on": "2026-08-18"},
            {"item": "A", "active_on": date(2026, 8, 18), "limit": 7},
        ),
    ],
)
def test_executor_normalizes_stage_6_tools(
    tool: str,
    arguments: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=7))

    payload, trace = executor.execute(tool, arguments)

    assert repository.arguments == expected
    assert trace.tool == tool
    assert trace.records_returned == 1
    assert payload["data"]


def test_executor_normalizes_parameters_filters() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=6))

    payload, trace = executor.execute(
        "consultar_parametros",
        {"item": "A", "location": "13", "supplier": "101", "limit": 50},
    )

    assert repository.arguments == {
        "item": "A",
        "location": 13,
        "supplier": 101,
        "limit": 6,
    }
    assert trace.tool == "consultar_parametros"
    assert payload["data"][0]["lead_time_days"] == 2


def test_executor_does_not_inject_limit_into_executions() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings())

    payload, trace = executor.execute("consultar_ejecuciones", {"phase": "13.1"})

    assert repository.arguments == {"phase": "13.1"}
    assert trace.tool == "consultar_ejecuciones"
    assert payload["data"][0]["status"] == "SUCCESS"


def test_executor_normalizes_model_metrics_arguments() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings(assistant_max_records=6))

    executor.execute(
        "consultar_metricas_modelo",
        {"dataset": "validation", "evaluation_level": "period", "horizon_day": "2", "limit": 20},
    )

    assert repository.arguments == {
        "dataset": "validation",
        "evaluation_level": "period",
        "horizon_day": 2,
        "limit": 6,
    }


@pytest.mark.parametrize(
    ("tool", "maximum"),
    [
        ("consultar_shap_global", 15),
        ("consultar_shap_horizontes", 15),
        ("consultar_shap_local", 10),
    ],
)
def test_executor_clamps_shap_top_n(tool: str, maximum: int) -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings())
    arguments: dict[str, Any] = {"top_n": 99}
    if tool == "consultar_shap_local":
        arguments["sample_id"] = "S1"

    executor.execute(tool, arguments)

    assert repository.arguments["top_n"] == maximum


def test_executor_normalizes_shap_local_composite_key() -> None:
    repository = FakeRepository()
    executor = ToolExecutor(repository, assistant_settings())

    executor.execute(
        "consultar_shap_local",
        {
            "item_code": "101",
            "location_code": "13",
            "target_date": "2026-08-18",
            "horizon_day": "2",
        },
    )

    assert repository.arguments["item_code"] == 101
    assert repository.arguments["location_code"] == 13
    assert repository.arguments["target_date"] == date(2026, 8, 18)
    assert repository.arguments["horizon_day"] == 2


def test_executor_rejects_incomplete_shap_local_key() -> None:
    executor = ToolExecutor(FakeRepository(), assistant_settings())

    with pytest.raises(ValueError, match="Indique sample_id"):
        executor.execute("consultar_shap_local", {"item_code": 101})
