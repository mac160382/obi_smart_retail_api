import pytest

from app.modules.assistant.tool_registry import (
    IMPLEMENTED_TOOL_NAMES,
    response_tools,
    validate_selected_tools,
)


def test_database_query_tools_are_implemented() -> None:
    assert IMPLEMENTED_TOOL_NAMES == {
        "consultar_pedidos_sugeridos",
        "consultar_pronosticos",
        "consultar_ventas",
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


def test_planned_tool_cannot_execute_before_implementation() -> None:
    with pytest.raises(ValueError, match="no implementada"):
        validate_selected_tools(
            ["consultar_promociones"],
            enabled_tools=["consultar_promociones"],
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
