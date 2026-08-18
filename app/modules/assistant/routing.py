from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.modules.assistant.tool_registry import validate_planned_tools

PROHIBITED_ACTION = re.compile(
    r"\b(reentrena|reentrenar|entrena|entrenar|recalcula|recalcular|"
    r"modifica|modificar|reemplaza|reemplazar|elimina|eliminar|borra|borrar|"
    r"inserta|insertar|actualiza|actualizar|ejecuta\s+sql|sql\s+libre)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteDecision:
    tools: tuple[str, ...] | None
    mode: str
    rule_id: str
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(normalize_text(term) in text for term in terms)


@lru_cache(maxsize=1)
def business_questions() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("business_questions.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) != 10:
        raise RuntimeError("business_questions.json debe contener diez preguntas.")
    return [dict(item) for item in value]


def public_questions() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "question": item["question"],
            "category": item["category"],
            "description": item["description"],
            "planned_tools": item["expected_tools"],
        }
        for item in business_questions()
    ]


def is_prohibited_action(question: str) -> bool:
    return bool(PROHIBITED_ACTION.search(normalize_text(question)))


def business_question_match(question: str) -> tuple[str, list[str]] | None:
    text = normalize_text(question)
    for entry in business_questions():
        if normalize_text(str(entry["question"])) == text:
            return str(entry["id"]), validate_planned_tools(entry["expected_tools"])

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for entry in business_questions():
        keywords = [normalize_text(str(term)) for term in entry.get("keywords", [])]
        score = sum(1 for keyword in keywords if keyword and keyword in text)
        if score:
            scored.append((score, len(keywords), entry))
    if not scored:
        return None
    scored.sort(key=lambda value: (value[0], value[1]), reverse=True)
    score, _, entry = scored[0]
    if score < 2:
        return None
    return str(entry["id"]), validate_planned_tools(entry["expected_tools"])


def _decision(tool: str, rule_id: str, explanation: str) -> RouteDecision:
    return RouteDecision(
        tools=(tool,),
        mode="automatic",
        rule_id=rule_id,
        explanation=explanation,
    )


def _catalog_intent(text: str, subjects: tuple[str, ...]) -> bool:
    return contains_any(text, subjects) and contains_any(
        text,
        ("catalogo", "maestro", "lista", "listar", "disponibles", "existentes"),
    )


def deterministic_route(question: str) -> RouteDecision:
    text = normalize_text(question)
    if is_prohibited_action(question):
        return RouteDecision(
            tools=None,
            mode="local_restriction",
            rule_id="restricted_action",
            explanation="La solicitud corresponde a una acción fuera del alcance de consulta.",
        )

    matched = business_question_match(question)
    if matched is not None:
        rule_id, tools = matched
        return RouteDecision(
            tools=tuple(tools),
            mode="business_question",
            rule_id=rule_id,
            explanation="La pregunta coincide con una pregunta de negocio definida.",
        )

    if "shap" in text or (
        contains_any(text, ("variable", "variables", "predictor", "factores"))
        and contains_any(text, ("importan", "contribu", "explica", "influyen"))
    ):
        if contains_any(text, ("local", "observacion", "prediccion individual")):
            return _decision(
                "consultar_shap_local", "shap_local", "Solicita una explicación local."
            )
        if "horizonte" in text:
            return _decision(
                "consultar_shap_horizontes",
                "shap_horizons",
                "Solicita explicaciones por horizonte.",
            )
        return _decision("consultar_shap_global", "shap_global", "Solicita una explicación global.")

    rules: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
        (
            ("metrica", "mae", "rmse", "wape", "mase", "rmsse"),
            "consultar_metricas_modelo",
            "model_metrics",
            "Solicita métricas del modelo.",
        ),
        (
            ("pedido sugerido", "pedidos sugeridos", "pedido recomendado", "reponer", "reposicion"),
            "consultar_pedidos_sugeridos",
            "suggested_orders",
            "Solicita pedidos sugeridos.",
        ),
        (
            ("pronost", "demanda prevista", "ventas esperadas"),
            "consultar_pronosticos",
            "forecasts",
            "Solicita cantidades pronosticadas.",
        ),
        (
            ("promocion", "promociones", "uplift", "aumento esperado"),
            "consultar_promociones",
            "promotions",
            "Solicita información promocional.",
        ),
        (
            (
                "ventas recientes",
                "ventas historicas",
                "historial de ventas",
                "se han comportado las ventas",
                "se han comportado",
            ),
            "consultar_ventas",
            "sales",
            "Solicita ventas observadas.",
        ),
        (
            ("inventario", "existencias", "stock", "en transito"),
            "consultar_inventario",
            "inventory",
            "Solicita información de inventario.",
        ),
        (
            ("parametro", "parametros", "lead time", "tiempo de entrega", "periodo de revision"),
            "consultar_parametros",
            "parameters",
            "Solicita parámetros de reposición.",
        ),
        (
            ("ejecucion", "ejecuciones", "ultima corrida", "estado de la fase"),
            "consultar_ejecuciones",
            "executions",
            "Solicita resultados de ejecución.",
        ),
    )
    for terms, tool, rule_id, explanation in rules:
        if contains_any(text, terms):
            return _decision(tool, rule_id, explanation)

    if _catalog_intent(text, ("articulo", "articulos", "producto", "productos")):
        return _decision(
            "consultar_articulos", "items_catalog", "Solicita el maestro de artículos."
        )
    if _catalog_intent(text, ("tienda", "tiendas", "localizacion", "localizaciones")):
        return _decision("consultar_tiendas", "stores_catalog", "Solicita el maestro de tiendas.")

    raise ValueError(
        "No pude identificar una fuente concreta. Pregunte por pronósticos, pedidos "
        "sugeridos, ventas, inventario, promociones, artículos, tiendas, métricas, "
        "explicaciones o ejecuciones."
    )


def resolve_route(question: str, explicit_tools: list[str] | None) -> RouteDecision:
    if is_prohibited_action(question):
        return deterministic_route(question)
    if explicit_tools is not None:
        return RouteDecision(
            tools=tuple(validate_planned_tools(explicit_tools)),
            mode="explicit",
            rule_id="application_selection",
            explanation="La aplicación proporcionó las funciones autorizadas.",
        )
    return deterministic_route(question)


def contextual_question(
    question: str,
    *,
    forecast_origin: str | None,
    decision: RouteDecision,
    user_context: dict[str, Any] | None,
) -> str:
    parts = [
        "Responde en español claro para un usuario de negocio.",
        "Cuando una fuente entregue una muestra, identifícala como muestra.",
        "Distingue contribución del modelo, asociación observada y causalidad.",
    ]
    if forecast_origin:
        parts.append(f"Origen seleccionado en la aplicación: {forecast_origin}.")
    if decision.tools and len(decision.tools) > 1:
        parts.append(
            "Utiliza todas estas funciones autorizadas antes de responder: "
            + ", ".join(decision.tools)
            + "."
        )
    if user_context:
        visible = {
            str(key): value for key, value in user_context.items() if value not in (None, "", [])
        }
        if visible:
            parts.append("Contexto proporcionado por la aplicación: " + repr(visible) + ".")
    parts.append("Pregunta del usuario: " + question.strip())
    return "\n\n".join(parts)
