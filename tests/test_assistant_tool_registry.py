import pytest

from app.modules.assistant.tool_registry import (
    IMPLEMENTED_TOOL_NAMES,
    response_tools,
    validate_selected_tools,
)


def test_forecasts_and_suggested_orders_are_implemented() -> None:
    assert IMPLEMENTED_TOOL_NAMES == {
        "consultar_pedidos_sugeridos",
        "consultar_pronosticos",
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
