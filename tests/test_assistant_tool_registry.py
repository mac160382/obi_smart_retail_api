import pytest

from app.modules.assistant.tool_registry import (
    IMPLEMENTED_TOOL_NAMES,
    response_tools,
    validate_selected_tools,
)


def test_database_query_tools_are_implemented() -> None:
    assert IMPLEMENTED_TOOL_NAMES == {
        "consultar_articulos",
        "consultar_inventario",
        "consultar_pedidos_sugeridos",
        "consultar_parametros",
        "consultar_promociones",
        "consultar_pronosticos",
        "consultar_tiendas",
        "consultar_ventas",
        "consultar_ejecuciones",
        "consultar_metricas_modelo",
        "consultar_shap_global",
        "consultar_shap_horizontes",
        "consultar_shap_local",
    }


def test_forecast_response_tool_has_closed_parameter_schema() -> None:
    tools = response_tools(
        ["consultar_pronosticos"],
        enabled_tools=["consultar_pronosticos"],
    )
    assert tools[0]["name"] == "consultar_pronosticos"
    assert tools[0]["parameters"]["additionalProperties"] is False
    assert "forecast_origin" in tools[0]["parameters"]["properties"]
    assert "target_date_from" in tools[0]["parameters"]["properties"]


def test_implemented_tool_must_be_enabled() -> None:
    with pytest.raises(ValueError, match="no habilitada"):
        validate_selected_tools(
            ["consultar_metricas_modelo"],
            enabled_tools=[],
        )


def test_sales_response_tool_exposes_supported_aggregations() -> None:
    tools = response_tools(
        ["consultar_ventas"],
        enabled_tools=["consultar_ventas"],
    )
    properties = tools[0]["parameters"]["properties"]
    assert properties["aggregation"]["enum"] == ["detail", "day", "week", None]
    assert "date_from" in properties
    assert "date_to" in properties


@pytest.mark.parametrize(
    ("tool", "expected_properties"),
    [
        ("consultar_articulos", {"item", "descripcion", "itemtype", "familia_cod", "limit"}),
        (
            "consultar_tiendas",
            {"location", "descripcion", "tipo_centro", "region", "estado", "limit"},
        ),
        (
            "consultar_inventario",
            {"item_code", "location_code", "proveedor_code", "estado_articulo", "limit"},
        ),
        ("consultar_parametros", {"item", "location", "supplier", "limit"}),
        ("consultar_promociones", {"item", "event_code", "status", "active_on", "limit"}),
        ("consultar_ejecuciones", {"phase"}),
        (
            "consultar_metricas_modelo",
            {"dataset", "evaluation_level", "horizon_day", "limit"},
        ),
        ("consultar_shap_global", {"predictor", "top_n"}),
        ("consultar_shap_horizontes", {"horizon_day", "top_n"}),
        (
            "consultar_shap_local",
            {"sample_id", "item_code", "location_code", "target_date", "horizon_day", "top_n"},
        ),
    ],
)
def test_stage_6_tools_have_closed_schemas(
    tool: str,
    expected_properties: set[str],
) -> None:
    registered = response_tools([tool], enabled_tools=[tool])[0]
    assert registered["parameters"]["additionalProperties"] is False
    assert set(registered["parameters"]["properties"]) == expected_properties
