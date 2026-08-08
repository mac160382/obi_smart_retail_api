from dataclasses import dataclass

from sqlalchemy import (
    Integer,
    and_,
    cast,
    delete,
    func,
    insert,
    literal,
    select,
    true,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.dml import Insert

from app.modules.imports.models import (
    g2_maestro_inventario_lacteos,
    pedido_sugerido,
    pronostico,
    vst_promociones_vigentes,
)

ADVISORY_LOCK_KEY = 7_183_001


class SuggestedOrderCalculationInProgressError(Exception):
    """Raised when another suggested-order calculation owns the lock."""


@dataclass(frozen=True)
class ReplacementCounts:
    deleted_rows: int
    inserted_rows: int


@dataclass(frozen=True)
class SuggestedOrderPageData:
    total_items: int
    items: list[dict[str, object]]


def build_suggested_orders_insert() -> Insert:
    latest_forecast_date = (
        select(
            func.max(pronostico.c.forecast_origin).label("forecast_origin")
        )
        .cte("ultima_fecha")
    )

    inventory = g2_maestro_inventario_lacteos
    location = cast(inventory.c.location_code, Integer)
    prediction = func.coalesce(pronostico.c.forecast_qty_vendida, 0)
    lead_time = func.coalesce(inventory.c.lead_time_days, 0)
    review_period = func.coalesce(inventory.c.review_period_days, 0)
    uplift = func.coalesce(vst_promociones_vigentes.c.uplift_esperado, 0)
    minimum_quantity = func.coalesce(
        inventory.c.minimum_handling_quantity_units,
        0,
    )
    current_stock = func.coalesce(inventory.c.current_stock_units, 0)
    in_transit = func.coalesce(inventory.c.on_order_in_transit_units, 0)
    suggested = func.coalesce(
        func.ceil(
            (prediction * (literal(1) - uplift) * literal(1))
            - minimum_quantity
            - current_stock
            - in_transit
        ),
        0,
    )

    calculated_rows = select(
        func.coalesce(inventory.c.item_code, ""),
        func.coalesce(location, 0),
        func.coalesce(inventory.c.description_location_code, ""),
        func.coalesce(inventory.c.description_item_code, ""),
        func.coalesce(inventory.c.description_proveedor, ""),
        prediction,
        lead_time,
        review_period,
        uplift,
        minimum_quantity,
        current_stock,
        in_transit,
        suggested,
        literal("Estimado", type_=pedido_sugerido.c.status.type),
        func.coalesce(
            pronostico.c.forecast_origin,
            latest_forecast_date.c.forecast_origin,
        ),
        func.coalesce(pronostico.c.horizon_day, 1),
        func.coalesce(
            pronostico.c.target_date,
            latest_forecast_date.c.forecast_origin,
        ),
    ).select_from(
        inventory.outerjoin(
            pronostico,
            and_(
                pronostico.c.item == inventory.c.item_code,
                pronostico.c.location == location,
            ),
        ).outerjoin(
            vst_promociones_vigentes,
            vst_promociones_vigentes.c.item == inventory.c.item_code,
        ).join(
            latest_forecast_date,
            true(),
        )
    )

    return insert(pedido_sugerido).from_select(
        [
            "item",
            "location",
            "descripcion_tienda",
            "descripcion_item",
            "descripcion_proveedor",
            "prediccion",
            "lead_time_days",
            "review_period_days",
            "uplift_esperado",
            "minimum_handling_quantity_units",
            "current_stock_units",
            "on_order_in_transit_units",
            "sugerido",
            "status",
            "forecast_origin",
            "horizon_day",
            "target_date",
        ],
        calculated_rows,
    )


def build_suggested_orders_page_query(
    location: int,
    page: int,
    page_size: int,
) -> Select:
    filtered_orders = (
        select(*pedido_sugerido.c)
        .where(
            pedido_sugerido.c.location == location,
            pedido_sugerido.c.horizon_day == 1,
        )
        .cte("filtered_orders")
    )
    page_rows = (
        select(*filtered_orders.c)
        .order_by(
            filtered_orders.c.item,
            filtered_orders.c.descripcion_tienda,
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
        .cte("page_rows")
    )
    totals = (
        select(func.count().label("total_items"))
        .select_from(filtered_orders)
        .cte("totals")
    )

    return (
        select(totals.c.total_items, *page_rows.c)
        .select_from(totals.outerjoin(page_rows, true()))
        .order_by(page_rows.c.item, page_rows.c.descripcion_tienda)
    )


class SuggestedOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_suggested_orders(self) -> ReplacementCounts:
        has_lock = self.db.scalar(
            select(func.pg_try_advisory_xact_lock(ADVISORY_LOCK_KEY))
        )
        if not has_lock:
            raise SuggestedOrderCalculationInProgressError

        deleted_result = self.db.execute(delete(pedido_sugerido))
        self.db.execute(build_suggested_orders_insert())
        inserted_rows = self.db.scalar(
            select(func.count()).select_from(pedido_sugerido)
        )

        return ReplacementCounts(
            deleted_rows=max(deleted_result.rowcount or 0, 0),
            inserted_rows=max(inserted_rows or 0, 0),
        )

    def get_by_location(
        self,
        location: int,
        page: int,
        page_size: int,
    ) -> SuggestedOrderPageData:
        rows = (
            self.db.execute(
                build_suggested_orders_page_query(location, page, page_size)
            )
            .mappings()
            .all()
        )
        total_items = int(rows[0]["total_items"]) if rows else 0
        column_names = [column.name for column in pedido_sugerido.c]
        items = [
            {name: row[name] for name in column_names}
            for row in rows
            if row["item"] is not None
        ]
        return SuggestedOrderPageData(
            total_items=total_items,
            items=items,
        )
