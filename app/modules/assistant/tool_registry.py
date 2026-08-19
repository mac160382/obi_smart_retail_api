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
IMPLEMENTED_TOOL_NAMES = frozenset(
    {
        "consultar_pedidos_sugeridos",
        "consultar_pronosticos",
        "consultar_articulos",
        "consultar_tiendas",
        "consultar_ventas",
        "consultar_inventario",
        "consultar_parametros",
        "consultar_promociones",
        "consultar_ejecuciones",
        "consultar_metricas_modelo",
        "consultar_shap_global",
        "consultar_shap_horizontes",
        "consultar_shap_local",
    }
)

DEFAULT_ARGUMENTS: dict[str, dict[str, Any]] = {
    "consultar_pronosticos": {"limit": 5},
    "consultar_pedidos_sugeridos": {"status": "Estimado", "limit": 5},
    "consultar_articulos": {"limit": 10},
    "consultar_tiendas": {"limit": 10},
    "consultar_ventas": {"aggregation": "day", "limit": 10},
    "consultar_inventario": {"limit": 10},
    "consultar_parametros": {"limit": 10},
    "consultar_promociones": {"limit": 10},
    "consultar_ejecuciones": {},
    "consultar_metricas_modelo": {"dataset": "test", "limit": 10},
    "consultar_shap_global": {"top_n": 10},
    "consultar_shap_horizontes": {"top_n": 10},
    "consultar_shap_local": {"top_n": 10},
}

TOOL_ENDPOINTS = {
    "consultar_pronosticos": "/api/v1/forecasts",
    "consultar_pedidos_sugeridos": "/api/v1/suggested-orders",
    "consultar_articulos": "/api/v1/items",
    "consultar_tiendas": "/api/v1/stores",
    "consultar_ventas": "/api/v1/sales",
    "consultar_inventario": "/api/v1/inventory",
    "consultar_parametros": "/api/v1/parameters",
    "consultar_promociones": "/api/v1/promotions",
    "consultar_ejecuciones": "/api/v1/executions",
    "consultar_metricas_modelo": "/api/v1/model/metrics",
    "consultar_shap_global": "/api/v1/shap/global",
    "consultar_shap_horizontes": "/api/v1/shap/horizons",
    "consultar_shap_local": "/api/v1/shap/local",
}

TOOL_DESCRIPTIONS = {
    "consultar_pronosticos": (
        "Consulta pronósticos publicados por artículo, tienda, origen, fecha y horizonte."
    ),
    "consultar_pedidos_sugeridos": (
        "Consulta pedidos sugeridos, existencias, tránsito, proveedor, cantidad y estado."
    ),
    "consultar_articulos": "Consulta el maestro de artículos.",
    "consultar_tiendas": "Consulta el maestro de tiendas.",
    "consultar_ventas": ("Consulta ventas observadas con detalle o agregación diaria o semanal."),
    "consultar_inventario": "Consulta existencias, tránsito y atributos de inventario.",
    "consultar_parametros": "Consulta tiempos de entrega, revisión y parámetros de reposición.",
    "consultar_promociones": "Consulta promociones vigentes y la variación esperada.",
    "consultar_ejecuciones": "Consulta el estado disponible de ejecuciones registradas.",
    "consultar_metricas_modelo": "Consulta métricas ya calculadas del Random Forest global.",
    "consultar_shap_global": "Consulta importancia global SHAP ya calculada.",
    "consultar_shap_horizontes": "Consulta importancia SHAP ya calculada por horizonte.",
    "consultar_shap_local": "Consulta contribuciones SHAP locales ya calculadas.",
}


def _nullable(kind: str, description: str, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"type": [kind, "null"], "description": description}
    value.update(extra)
    return value


TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "consultar_pronosticos": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "item_code": _nullable("integer", "Código interno del artículo."),
            "location": _nullable("integer", "Código de la tienda."),
            "location_code": _nullable("integer", "Código interno de la tienda."),
            "forecast_origin": _nullable("string", "Origen YYYY-MM-DD del pronóstico."),
            "target_date_from": _nullable("string", "Fecha objetivo inicial YYYY-MM-DD."),
            "target_date_to": _nullable("string", "Fecha objetivo final YYYY-MM-DD."),
            "horizon_day": _nullable("integer", "Horizonte entre 1 y 7.", minimum=1, maximum=7),
            "offset": _nullable("integer", "Posición inicial.", minimum=0),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
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
    },
    "consultar_articulos": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "descripcion": _nullable("string", "Texto de la descripción."),
            "itemtype": _nullable("integer", "Tipo de artículo."),
            "familia_cod": _nullable("integer", "Código de familia."),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_tiendas": {
        "type": "object",
        "properties": {
            "location": _nullable("integer", "Código de tienda."),
            "descripcion": _nullable("string", "Texto de la descripción."),
            "tipo_centro": _nullable("string", "Tipo de centro."),
            "region": _nullable("string", "Región."),
            "estado": _nullable("integer", "Estado de la tienda."),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_ventas": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "location": _nullable("integer", "Código de la tienda."),
            "date_from": _nullable("string", "Fecha inicial YYYY-MM-DD."),
            "date_to": _nullable("string", "Fecha final YYYY-MM-DD."),
            "aggregation": _nullable(
                "string",
                "Nivel de detalle: detail, day o week.",
                enum=["detail", "day", "week", None],
            ),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_inventario": {
        "type": "object",
        "properties": {
            "item_code": _nullable("string", "Código del artículo en inventario."),
            "location_code": _nullable("string", "Código de tienda en inventario."),
            "proveedor_code": _nullable("string", "Código de proveedor."),
            "estado_articulo": _nullable("string", "Estado del artículo."),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_parametros": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "location": _nullable("integer", "Código de tienda."),
            "supplier": _nullable("integer", "Código de proveedor."),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_promociones": {
        "type": "object",
        "properties": {
            "item": _nullable("string", "Código del artículo."),
            "event_code": _nullable("string", "Código del acontecimiento promocional."),
            "status": _nullable("string", "Estado de la promoción."),
            "active_on": _nullable("string", "Fecha YYYY-MM-DD dentro de la promoción."),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_ejecuciones": {
        "type": "object",
        "properties": {
            "phase": _nullable("string", "Fase que se desea consultar."),
        },
        "additionalProperties": False,
    },
    "consultar_metricas_modelo": {
        "type": "object",
        "properties": {
            "dataset": _nullable(
                "string",
                "Conjunto validation o test.",
                enum=["validation", "test", None],
            ),
            "evaluation_level": _nullable("string", "Nivel de evaluación."),
            "horizon_day": _nullable("integer", "Horizonte entre 1 y 7.", minimum=1, maximum=7),
            "limit": _nullable("integer", "Cantidad máxima de registros.", minimum=1, maximum=25),
        },
        "additionalProperties": False,
    },
    "consultar_shap_global": {
        "type": "object",
        "properties": {
            "predictor": _nullable("string", "Nombre de un predictor."),
            "top_n": _nullable("integer", "Cantidad de predictores.", minimum=1, maximum=15),
        },
        "additionalProperties": False,
    },
    "consultar_shap_horizontes": {
        "type": "object",
        "properties": {
            "horizon_day": _nullable("integer", "Horizonte entre 1 y 7.", minimum=1, maximum=7),
            "top_n": _nullable("integer", "Cantidad por horizonte.", minimum=1, maximum=15),
        },
        "additionalProperties": False,
    },
    "consultar_shap_local": {
        "type": "object",
        "properties": {
            "sample_id": _nullable("string", "Identificador de la observación SHAP."),
            "item_code": _nullable("integer", "Código interno del artículo."),
            "location_code": _nullable("integer", "Código interno de tienda."),
            "target_date": _nullable("string", "Fecha objetivo YYYY-MM-DD."),
            "horizon_day": _nullable("integer", "Horizonte entre 1 y 7.", minimum=1, maximum=7),
            "top_n": _nullable("integer", "Cantidad de contribuciones.", minimum=1, maximum=10),
        },
        "additionalProperties": False,
    },
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
