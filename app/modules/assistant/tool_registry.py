from collections.abc import Iterable
from typing import Any

PLANNED_TOOL_NAMES = frozenset(
    {
        "consultar_pronosticos",
        "consultar_pedidos_sugeridos",
        "consultar_articulos",
        "consultar_tiendas",
        "consultar_ventas",
        "consultar_inventario",
        "consultar_parametros",
        "consultar_promociones",
        "consultar_metricas_modelo",
        "consultar_shap_global",
        "consultar_shap_horizontes",
        "consultar_shap_local",
        "consultar_ejecuciones",
    }
)
IMPLEMENTED_TOOL_NAMES = frozenset({"consultar_pedidos_sugeridos"})

DEFAULT_ARGUMENTS: dict[str, dict[str, Any]] = {
    "consultar_pedidos_sugeridos": {"status": "Estimado", "limit": 5},
}

TOOL_ENDPOINTS = {
    "consultar_pedidos_sugeridos": "/api/v1/suggested-orders",
}

TOOL_DESCRIPTIONS = {
    "consultar_pedidos_sugeridos": (
        "Consulta pedidos sugeridos, existencias, tránsito, proveedor, cantidad y estado."
    ),
}


def _nullable(kind: str, description: str, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"type": [kind, "null"], "description": description}
    value.update(extra)
    return value


TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "consultar_pedidos_sugeridos": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "location": _nullable("integer", "Código de la tienda."),
            "status": _nullable(
                "string",
                "Estado Estimado, Planificado o Aprobado.",
                enum=["Estimado", "Planificado", "Aprobado", None],
            ),
            "forecast_origin": _nullable("string", "Origen YYYY-MM-DD del pronóstico."),
            "target_date": _nullable("string", "Fecha objetivo YYYY-MM-DD."),
            "horizon_day": _nullable("integer", "Horizonte entre 1 y 7.", minimum=1, maximum=7),
            "order_type": _nullable(
                "string",
                "Filtra pedidos positivos, en cero o todos.",
                enum=["positive", "zero", "all", None],
            ),
            "offset": _nullable("integer", "Posición inicial.", minimum=0),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    }
}


def validate_selected_tools(
    names: Iterable[str],
    *,
    enabled_tools: Iterable[str] | None = None,
) -> list[str]:
    enabled = IMPLEMENTED_TOOL_NAMES if enabled_tools is None else frozenset(enabled_tools)
    selected: list[str] = []
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        if name not in IMPLEMENTED_TOOL_NAMES:
            raise ValueError(f"Función no implementada: {name}")
        if name not in enabled:
            raise ValueError(f"Función no habilitada: {name}")
        if name not in selected:
            selected.append(name)
    if not selected:
        raise ValueError("Debe seleccionarse al menos una función habilitada.")
    return selected


def validate_planned_tools(names: Iterable[str]) -> list[str]:
    selected: list[str] = []
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        if name not in PLANNED_TOOL_NAMES:
            raise ValueError(f"Función no autorizada: {name}")
        if name not in selected:
            selected.append(name)
    if not selected:
        raise ValueError("Debe seleccionarse al menos una función autorizada.")
    return selected


def response_tools(
    names: Iterable[str],
    *,
    enabled_tools: Iterable[str],
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "parameters": TOOL_PARAMETERS[name],
            "strict": False,
        }
        for name in validate_selected_tools(names, enabled_tools=enabled_tools)
    ]
