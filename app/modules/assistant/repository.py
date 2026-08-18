from datetime import date
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.imports.models import pedido_sugerido


class AssistantQueryRepository:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

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
