import pytest

from app.modules.assistant.routing import (
    business_questions,
    deterministic_route,
    resolve_route,
)


def test_all_business_questions_resolve_to_planned_tools() -> None:
    for entry in business_questions():
        decision = deterministic_route(str(entry["question"]))
        assert list(decision.tools or ()) == entry["expected_tools"]
        assert decision.mode == "business_question"


def test_restricted_action_is_resolved_locally() -> None:
    decision = deterministic_route("Recalcula y reemplaza todos los pedidos sugeridos")
    assert decision.tools is None
    assert decision.mode == "local_restriction"


def test_explicit_planned_tool_is_preserved() -> None:
    decision = resolve_route(
        "Consulta controlada",
        explicit_tools=["consultar_pedidos_sugeridos"],
    )
    assert decision.tools == ("consultar_pedidos_sugeridos",)
    assert decision.mode == "explicit"


def test_unknown_question_is_rejected() -> None:
    with pytest.raises(ValueError, match="No pude identificar"):
        deterministic_route("Cuéntame algo interesante")


def test_unknown_explicit_tool_is_rejected() -> None:
    with pytest.raises(ValueError, match="no autorizada"):
        resolve_route("Consulta", explicit_tools=["ejecutar_sql"])


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("Lista los artículos existentes", "consultar_articulos"),
        ("Lista las tiendas disponibles", "consultar_tiendas"),
        ("Consulta el stock del inventario", "consultar_inventario"),
        ("Consulta las promociones vigentes", "consultar_promociones"),
    ],
)
def test_stage_6_questions_route_to_expected_tool(question: str, tool: str) -> None:
    decision = deterministic_route(question)
    assert decision.tools == (tool,)
