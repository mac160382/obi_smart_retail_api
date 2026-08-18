from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal, Protocol, cast

from app.core.config import Settings
from app.modules.assistant.tool_registry import (
    DEFAULT_ARGUMENTS,
    TOOL_ENDPOINTS,
    TOOL_PARAMETERS,
    validate_selected_tools,
)


class AssistantDataReader(Protocol):
    def get_sales(
        self,
        *,
        item: str | None = None,
        location: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        aggregation: Literal["detail", "day", "week"] = "day",
        limit: int = 10,
    ) -> dict[str, Any]: ...

    def get_forecasts(
        self,
        *,
        item: str | None = None,
        item_code: int | None = None,
        location: int | None = None,
        location_code: int | None = None,
        forecast_origin: date | None = None,
        target_date_from: date | None = None,
        target_date_to: date | None = None,
        horizon_day: int | None = None,
        offset: int = 0,
        limit: int = 5,
    ) -> dict[str, Any]: ...

    def get_suggested_orders(
        self,
        *,
        item: str | None = None,
        location: int | None = None,
        status: str | None = None,
        forecast_origin: date | None = None,
        target_date: date | None = None,
        horizon_day: int | None = None,
        order_type: Literal["positive", "zero", "all"] = "all",
        offset: int = 0,
        limit: int = 5,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ToolTrace:
    tool: str
    endpoint: str
    arguments: dict[str, Any]
    source: Any
    records_returned: int | None
    http_status: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolExecutor:
    def __init__(self, repository: AssistantDataReader, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    @property
    def enabled_tools(self) -> tuple[str, ...]:
        return self.settings.assistant_enabled_tool_names

    @staticmethod
    def _optional_date(value: Any, name: str) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError(f"{name} debe usar el formato YYYY-MM-DD.") from exc

    def normalize_arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        validate_selected_tools([name], enabled_tools=self.enabled_tools)
        allowed = set(TOOL_PARAMETERS[name]["properties"])
        unexpected = sorted(set(arguments) - allowed)
        if unexpected:
            raise ValueError(
                f"La función {name} recibió argumentos no permitidos: {', '.join(unexpected)}."
            )
        clean = {
            key: value for key, value in arguments.items() if value is not None and value != ""
        }
        for key, value in DEFAULT_ARGUMENTS[name].items():
            clean.setdefault(key, value)

        clean["limit"] = min(
            max(int(clean.get("limit", 5)), 1),
            self.settings.assistant_max_records,
        )
        if "offset" in allowed:
            clean["offset"] = min(max(int(clean.get("offset", 0)), 0), 1_000_000)
        for field in ("item_code", "location", "location_code"):
            if field in clean:
                clean[field] = int(clean[field])
        if "horizon_day" in clean:
            clean["horizon_day"] = min(max(int(clean["horizon_day"]), 1), 7)
        for field in (
            "forecast_origin",
            "target_date",
            "target_date_from",
            "target_date_to",
            "date_from",
            "date_to",
        ):
            if field in clean:
                clean[field] = self._optional_date(clean[field], field)

        if name == "consultar_pronosticos":
            date_from = clean.get("target_date_from")
            date_to = clean.get("target_date_to")
            if date_from is not None and date_to is not None and date_from > date_to:
                raise ValueError("target_date_from no puede ser posterior a target_date_to.")
        elif name == "consultar_ventas":
            date_from = clean.get("date_from")
            date_to = clean.get("date_to")
            if date_from is not None and date_to is not None and date_from > date_to:
                raise ValueError("date_from no puede ser posterior a date_to.")
            aggregation = str(clean.get("aggregation", "day"))
            if aggregation not in {"detail", "day", "week"}:
                raise ValueError("aggregation debe ser detail, day o week.")
            clean["aggregation"] = cast(Literal["detail", "day", "week"], aggregation)
        elif name == "consultar_pedidos_sugeridos":
            order_type = str(clean.get("order_type", "all"))
            if order_type not in {"positive", "zero", "all"}:
                raise ValueError("order_type debe ser positive, zero o all.")
            clean["order_type"] = cast(Literal["positive", "zero", "all"], order_type)
            status = clean.get("status")
            if status not in {None, "Estimado", "Planificado", "Aprobado"}:
                raise ValueError("status debe ser Estimado, Planificado o Aprobado.")
        return clean

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], ToolTrace]:
        normalized = self.normalize_arguments(name, arguments)
        handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "consultar_pronosticos": self.repository.get_forecasts,
            "consultar_pedidos_sugeridos": self.repository.get_suggested_orders,
            "consultar_ventas": self.repository.get_sales,
        }
        payload = handlers[name](**normalized)
        meta = payload.get("meta", {})
        return payload, ToolTrace(
            tool=name,
            endpoint=TOOL_ENDPOINTS[name],
            arguments=normalized,
            source=meta.get("source"),
            records_returned=meta.get("records_returned"),
            http_status=200,
        )

    @staticmethod
    def compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
        meta = dict(payload.get("meta", {}))
        compact_meta = {
            key: meta.get(key)
            for key in (
                "endpoint",
                "source",
                "filters_applied",
                "records_returned",
                "total_matching",
                "has_more",
            )
            if key in meta
        }
        return {"meta": compact_meta, "data": payload.get("data")}
