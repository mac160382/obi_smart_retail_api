import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import Date as SQLDate
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.imports.models import (
    g2_lacteos_promociones_vigentes,
    g2_maestro_inventario_lacteos,
    lacteos_maestro_items,
    lacteos_maestro_tiendas,
    lacteos_ventas_historicas,
    pedido_sugerido,
    pronostico,
)


class AssistantQueryRepository:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def get_items(
        self,
        *,
        item: str | None = None,
        descripcion: str | None = None,
        itemtype: int | None = None,
        familia_cod: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        items = lacteos_maestro_items
        conditions: list[Any] = []
        if item is not None:
            conditions.append(items.c.item == item)
        if descripcion is not None:
            conditions.append(items.c.descripcion.ilike(f"%{descripcion}%"))
        if itemtype is not None:
            conditions.append(items.c.itemtype == itemtype)
        if familia_cod is not None:
            conditions.append(items.c.familia_cod == familia_cod)

        query = select(*items.c).where(*conditions).order_by(items.c.item).limit(limit)
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item": item,
            "descripcion": descripcion,
            "itemtype": itemtype,
            "familia_cod": familia_cod,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/items",
                "source": f"{self.settings.items_master_schema}.{self.settings.items_master_table}",
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
            },
            "data": rows,
        }

    def get_stores(
        self,
        *,
        location: int | None = None,
        descripcion: str | None = None,
        tipo_centro: str | None = None,
        region: str | None = None,
        estado: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        stores = lacteos_maestro_tiendas
        conditions: list[Any] = []
        if location is not None:
            conditions.append(stores.c.location == location)
        if descripcion is not None:
            conditions.append(stores.c.descripcion.ilike(f"%{descripcion}%"))
        if tipo_centro is not None:
            conditions.append(stores.c.tipo_centro == tipo_centro)
        if region is not None:
            conditions.append(stores.c.region == region)
        if estado is not None:
            conditions.append(stores.c.estado == estado)

        query = select(*stores.c).where(*conditions).order_by(stores.c.location).limit(limit)
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "location": location,
            "descripcion": descripcion,
            "tipo_centro": tipo_centro,
            "region": region,
            "estado": estado,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/stores",
                "source": (
                    f"{self.settings.stores_master_schema}.{self.settings.stores_master_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
            },
            "data": rows,
        }

    def get_inventory(
        self,
        *,
        item_code: str | None = None,
        location_code: str | None = None,
        proveedor_code: str | None = None,
        estado_articulo: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        inventory = g2_maestro_inventario_lacteos
        conditions: list[Any] = []
        if item_code is not None:
            conditions.append(inventory.c.item_code == item_code)
        if location_code is not None:
            conditions.append(inventory.c.location_code == location_code)
        if proveedor_code is not None:
            conditions.append(inventory.c.proveedor_code == proveedor_code)
        if estado_articulo is not None:
            conditions.append(inventory.c.estado_articulo == estado_articulo)

        query = (
            select(*inventory.c)
            .where(*conditions)
            .order_by(inventory.c.item_code, inventory.c.location_code)
            .limit(limit)
        )
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item_code": item_code,
            "location_code": location_code,
            "proveedor_code": proveedor_code,
            "estado_articulo": estado_articulo,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/inventory",
                "source": (
                    f"{self.settings.inventory_master_schema}."
                    f"{self.settings.inventory_master_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
            },
            "data": rows,
        }

    def get_parameters(
        self,
        *,
        item: str | None = None,
        location: int | None = None,
        supplier: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        inventory = g2_maestro_inventario_lacteos
        conditions: list[Any] = []
        if item is not None:
            conditions.append(inventory.c.item_code == item)
        if location is not None:
            conditions.append(inventory.c.location_code == str(location))
        if supplier is not None:
            conditions.append(inventory.c.proveedor_code == str(supplier))

        query = (
            select(
                inventory.c.item_code.label("item"),
                inventory.c.description_item_code.label("descripcion_item"),
                inventory.c.location_code.label("location"),
                inventory.c.description_location_code.label("descripcion_tienda"),
                inventory.c.proveedor_code.label("supplier"),
                inventory.c.description_proveedor.label("descripcion_proveedor"),
                inventory.c.service_level,
                inventory.c.frecuencia_pedido,
                inventory.c.minimum_handling_quantity_units,
                inventory.c.lead_time_days,
                inventory.c.review_period_days,
            )
            .where(*conditions)
            .order_by(inventory.c.item_code, inventory.c.location_code)
            .limit(limit)
        )
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item": item,
            "location": location,
            "supplier": supplier,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/parameters",
                "source": (
                    f"{self.settings.inventory_master_schema}."
                    f"{self.settings.inventory_master_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
            },
            "data": rows,
        }

    @staticmethod
    def _execution_summary(path: Path, item: dict[str, Any]) -> dict[str, Any]:
        base = {
            "phase": item.get("phase"),
            "process": item.get("process"),
            "source_file": path.name,
        }
        if not path.is_file():
            return {**base, "available": False, "status": None}

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

        def value_for(prefix: str) -> str | None:
            return next(
                (line.split(":", 1)[1].strip() for line in lines if line.startswith(prefix)),
                None,
            )

        return {
            **base,
            "available": True,
            "status": value_for("Status:"),
            "started": value_for("Inicio UTC:"),
            "finished": value_for("Fin UTC:"),
            "modified_utc": datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=UTC,
            ).isoformat(),
        }

    def get_executions(self, *, phase: str | None = None) -> dict[str, Any]:
        execution_dir = self.settings.assistant_execution_dir.resolve()
        manifest_path = execution_dir / "execution_manifest.json"
        manifest: list[Any] = []
        if manifest_path.is_file():
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, list):
                raise ValueError("execution_manifest.json debe contener una lista.")
            manifest = parsed

        data: list[dict[str, Any]] = []
        sources: list[str] = []
        for raw_item in manifest:
            if not isinstance(raw_item, dict):
                raise ValueError("Cada entrada del manifiesto de ejecuciones debe ser un objeto.")
            item = dict(raw_item)
            filename = str(item.get("filename", "")).strip()
            if not filename:
                continue
            path = (execution_dir / filename).resolve()
            if not path.is_relative_to(execution_dir):
                raise ValueError("El manifiesto contiene una ruta fuera del directorio autorizado.")
            sources.append(filename)
            data.append(self._execution_summary(path, item))

        if phase is not None:
            data = [row for row in data if str(row.get("phase")) == phase]
        return {
            "meta": {
                "endpoint": "/api/v1/executions",
                "source": sources,
                "filters_applied": {"phase": phase} if phase is not None else {},
                "records_returned": len(data),
            },
            "data": data,
        }

    def get_promotions(
        self,
        *,
        item: str | None = None,
        event_code: str | None = None,
        status: str | None = None,
        active_on: date | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        promotions = g2_lacteos_promociones_vigentes
        conditions: list[Any] = []
        if item is not None:
            conditions.append(promotions.c.item == item)
        if event_code is not None:
            conditions.append(promotions.c.event_code == event_code)
        if status is not None:
            conditions.append(promotions.c.status == status)
        if active_on is not None:
            conditions.extend(
                [promotions.c.inicio <= active_on, promotions.c.fin >= active_on]
            )

        query = (
            select(*promotions.c)
            .where(*conditions)
            .order_by(promotions.c.inicio.desc(), promotions.c.item)
            .limit(limit)
        )
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item": item,
            "event_code": event_code,
            "status": status,
            "active_on": active_on,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/promotions",
                "source": (
                    f"{self.settings.current_promotions_schema}."
                    f"{self.settings.current_promotions_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
            },
            "data": rows,
        }

    def get_sales(
        self,
        *,
        item: str | None = None,
        location: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        aggregation: Literal["detail", "day", "week"] = "day",
        limit: int = 10,
    ) -> dict[str, Any]:
        sales = lacteos_ventas_historicas
        conditions: list[Any] = []
        if item is not None:
            conditions.append(sales.c.item == item)
        if location is not None:
            conditions.append(sales.c.location == location)
        if date_from is not None:
            conditions.append(sales.c.fecha >= date_from)
        if date_to is not None:
            conditions.append(sales.c.fecha <= date_to)

        if aggregation == "detail":
            query = (
                select(
                    sales.c.fecha,
                    sales.c.item,
                    sales.c.descripcion_item,
                    sales.c.location,
                    sales.c.descripcion_tienda,
                    sales.c.tipo_centro,
                    sales.c.qty_vendida,
                )
                .where(*conditions)
                .order_by(sales.c.fecha.desc(), sales.c.item, sales.c.location)
            )
        elif aggregation == "day":
            query = (
                select(
                    sales.c.fecha,
                    sales.c.item,
                    sales.c.location,
                    func.max(sales.c.descripcion_item).label("descripcion_item"),
                    func.max(sales.c.descripcion_tienda).label("descripcion_tienda"),
                    func.sum(sales.c.qty_vendida).label("qty_vendida"),
                )
                .where(*conditions)
                .group_by(sales.c.fecha, sales.c.item, sales.c.location)
                .order_by(sales.c.fecha.desc(), sales.c.item, sales.c.location)
            )
        else:
            week_start = cast(func.date_trunc("week", sales.c.fecha), SQLDate).label("week_start")
            query = (
                select(
                    week_start,
                    sales.c.item,
                    sales.c.location,
                    func.max(sales.c.descripcion_item).label("descripcion_item"),
                    func.max(sales.c.descripcion_tienda).label("descripcion_tienda"),
                    func.sum(sales.c.qty_vendida).label("qty_vendida"),
                )
                .where(*conditions)
                .group_by(week_start, sales.c.item, sales.c.location)
                .order_by(week_start.desc(), sales.c.item, sales.c.location)
            )

        rows = [dict(row) for row in self.db.execute(query.limit(limit)).mappings().all()]
        filters = {
            "item": item,
            "location": location,
            "date_from": date_from,
            "date_to": date_to,
            "aggregation": aggregation,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/sales",
                "source": (
                    f"{self.settings.database_schema}.{self.settings.historical_sales_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
                "aggregation": aggregation,
            },
            "data": rows,
        }

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
    ) -> dict[str, Any]:
        conditions: list[Any] = []
        if item is not None:
            conditions.append(pronostico.c.item == item)
        if item_code is not None:
            conditions.append(pronostico.c.item_code == item_code)
        if location is not None:
            conditions.append(pronostico.c.location == location)
        if location_code is not None:
            conditions.append(pronostico.c.location_code == location_code)
        if forecast_origin is not None:
            conditions.append(pronostico.c.forecast_origin == forecast_origin)
        if target_date_from is not None:
            conditions.append(pronostico.c.target_date >= target_date_from)
        if target_date_to is not None:
            conditions.append(pronostico.c.target_date <= target_date_to)
        if horizon_day is not None:
            conditions.append(pronostico.c.horizon_day == horizon_day)

        count_query = select(func.count()).select_from(pronostico).where(*conditions)
        total = int(self.db.scalar(count_query) or 0)
        query = (
            select(*pronostico.c)
            .where(*conditions)
            .order_by(
                pronostico.c.forecast_origin.desc(),
                pronostico.c.target_date,
                pronostico.c.item,
                pronostico.c.location,
            )
            .limit(limit)
            .offset(offset)
        )
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item": item,
            "item_code": item_code,
            "location": location,
            "location_code": location_code,
            "forecast_origin": forecast_origin,
            "target_date_from": target_date_from,
            "target_date_to": target_date_to,
            "horizon_day": horizon_day,
            "offset": offset,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/forecasts",
                "source": f"{self.settings.forecast_schema}.{self.settings.forecast_table}",
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
                "total_matching": total,
                "offset": offset,
                "has_more": offset + len(rows) < total,
            },
            "data": rows,
        }

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
    ) -> dict[str, Any]:
        conditions: list[Any] = []
        if item is not None:
            conditions.append(pedido_sugerido.c.item == item)
        if location is not None:
            conditions.append(pedido_sugerido.c.location == location)
        if status is not None:
            conditions.append(pedido_sugerido.c.status == status)
        if forecast_origin is not None:
            conditions.append(pedido_sugerido.c.forecast_origin == forecast_origin)
        if target_date is not None:
            conditions.append(pedido_sugerido.c.target_date == target_date)
        if horizon_day is not None:
            conditions.append(pedido_sugerido.c.horizon_day == horizon_day)
        if order_type == "positive":
            conditions.append(pedido_sugerido.c.sugerido > 0)
        elif order_type == "zero":
            conditions.append(pedido_sugerido.c.sugerido == 0)

        count_query = select(func.count()).select_from(pedido_sugerido).where(*conditions)
        total = int(self.db.scalar(count_query) or 0)
        query = (
            select(*pedido_sugerido.c)
            .where(*conditions)
            .order_by(
                pedido_sugerido.c.forecast_origin.desc(),
                pedido_sugerido.c.target_date,
                pedido_sugerido.c.item,
                pedido_sugerido.c.location,
            )
            .limit(limit)
            .offset(offset)
        )
        rows = [dict(row) for row in self.db.execute(query).mappings().all()]
        filters = {
            "item": item,
            "location": location,
            "status": status,
            "forecast_origin": forecast_origin,
            "target_date": target_date,
            "horizon_day": horizon_day,
            "order_type": order_type,
            "offset": offset,
            "limit": limit,
        }
        return {
            "meta": {
                "endpoint": "/api/v1/suggested-orders",
                "source": (
                    f"{self.settings.suggested_orders_schema}."
                    f"{self.settings.suggested_orders_table}"
                ),
                "filters_applied": {
                    key: value for key, value in filters.items() if value is not None
                },
                "records_returned": len(rows),
                "total_matching": total,
                "offset": offset,
                "has_more": offset + len(rows) < total,
            },
            "data": rows,
        }
