from datetime import date
from typing import Any, Literal

from sqlalchemy import Date as SQLDate
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.imports.models import (
    lacteos_ventas_historicas,
    pedido_sugerido,
    pronostico,
)


class AssistantQueryRepository:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

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
