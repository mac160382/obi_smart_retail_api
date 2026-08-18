from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

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
    update,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select
from sqlalchemy.sql.dml import Insert

from app.modules.imports.models import (
    g2_maestro_inventario_lacteos,
    pedido_sugerido,
    pedido_sugerido_historial,
    pronostico,
    vst_promociones_vigentes,
)

ADVISORY_LOCK_KEY = 7_183_001


class SuggestedOrderCalculationInProgressError(Exception):
    """Raised when another suggested-order calculation owns the lock."""


@dataclass(frozen=True)
class SuggestedOrderKey:
    item: str
    location: int
    forecast_origin: date
    horizon_day: int = 1


class SuggestedOrderNotFoundError(Exception):
    def __init__(self, key: SuggestedOrderKey) -> None:
        self.key = key
        super().__init__("Suggested order was not found")


class SuggestedOrderAlreadyApprovedError(Exception):
    def __init__(self, key: SuggestedOrderKey) -> None:
        self.key = key
        super().__init__("Suggested order is already approved")


@dataclass(frozen=True)
class SuggestedOrderUpdateCommand:
    key: SuggestedOrderKey
    ajustado: float
    observaciones: str


@dataclass(frozen=True)
class ReplacementCounts:
    deleted_rows: int
    inserted_rows: int


@dataclass(frozen=True)
class SuggestedOrderPageData:
    total_items: int
    items: list[dict[str, object]]


@dataclass(frozen=True)
class SuggestedOrderBatchData:
    batch_id: UUID
    updated_at: datetime
    items: list[dict[str, object]]


@dataclass(frozen=True)
class SuggestedOrderHistoryPageData:
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
    approved_orders = pedido_sugerido.alias("approved_orders")
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
    forecast_origin = func.coalesce(
        pronostico.c.forecast_origin,
        latest_forecast_date.c.forecast_origin,
    )
    horizon_day = func.coalesce(pronostico.c.horizon_day, 1)
    approved_order_exists = (
        select(literal(1))
        .select_from(approved_orders)
        .where(
            approved_orders.c.item == inventory.c.item_code,
            approved_orders.c.location == location,
            approved_orders.c.forecast_origin == forecast_origin,
            approved_orders.c.horizon_day == horizon_day,
            approved_orders.c.status == "Aprobado",
        )
        .exists()
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
        forecast_origin,
        horizon_day,
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
    ).where(~approved_order_exists)

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
    forecast_origin: date | None = None,
) -> Select:
    filters = [
        pedido_sugerido.c.location == location,
        pedido_sugerido.c.horizon_day == 1,
    ]
    if forecast_origin is not None:
        filters.append(
            pedido_sugerido.c.forecast_origin == forecast_origin
        )
    filtered_orders = (
        select(*pedido_sugerido.c)
        .where(*filters)
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

    def _acquire_write_lock(self) -> None:
        has_lock = self.db.scalar(
            select(func.pg_try_advisory_xact_lock(ADVISORY_LOCK_KEY))
        )
        if not has_lock:
            raise SuggestedOrderCalculationInProgressError

    def replace_suggested_orders(self) -> ReplacementCounts:
        self._acquire_write_lock()

        deleted_result = self.db.execute(
            delete(pedido_sugerido).where(
                pedido_sugerido.c.status != "Aprobado"
            )
        )
        inserted_result = self.db.execute(build_suggested_orders_insert())

        return ReplacementCounts(
            deleted_rows=max(deleted_result.rowcount or 0, 0),
            inserted_rows=max(inserted_result.rowcount or 0, 0),
        )

    def approve_batch(
        self,
        commands: list[SuggestedOrderUpdateCommand],
        user_id: UUID,
        batch_id: UUID,
        modified_at: datetime,
    ) -> SuggestedOrderBatchData:
        self._acquire_write_lock()
        locked_rows: list[tuple[SuggestedOrderUpdateCommand, dict[str, object]]] = []

        for command in commands:
            key = command.key
            row = self.db.execute(
                select(*pedido_sugerido.c)
                .where(
                    pedido_sugerido.c.item == key.item,
                    pedido_sugerido.c.location == key.location,
                    pedido_sugerido.c.forecast_origin == key.forecast_origin,
                    pedido_sugerido.c.horizon_day == key.horizon_day,
                )
                .with_for_update()
            ).mappings().one_or_none()
            if row is None:
                raise SuggestedOrderNotFoundError(key)
            current = dict(row)
            if current["status"] == "Aprobado":
                raise SuggestedOrderAlreadyApprovedError(key)
            locked_rows.append((command, current))

        history_rows = [
            {
                "change_id": uuid4(),
                "batch_id": batch_id,
                "item": command.key.item,
                "location": command.key.location,
                "forecast_origin": command.key.forecast_origin,
                "horizon_day": command.key.horizon_day,
                "target_date": current["target_date"],
                "ajustado_anterior": current["ajustado"],
                "ajustado_nuevo": command.ajustado,
                "observaciones_anteriores": current["observaciones"],
                "observaciones_nuevas": command.observaciones,
                "status_anterior": current["status"],
                "status_nuevo": "Aprobado",
                "modified_by": user_id,
                "modified_at": modified_at,
            }
            for command, current in locked_rows
        ]
        self.db.execute(insert(pedido_sugerido_historial), history_rows)

        updated_items: list[dict[str, object]] = []
        for command, _current in locked_rows:
            key = command.key
            updated = self.db.execute(
                update(pedido_sugerido)
                .where(
                    pedido_sugerido.c.item == key.item,
                    pedido_sugerido.c.location == key.location,
                    pedido_sugerido.c.forecast_origin == key.forecast_origin,
                    pedido_sugerido.c.horizon_day == key.horizon_day,
                    pedido_sugerido.c.status != "Aprobado",
                )
                .values(
                    ajustado=command.ajustado,
                    observaciones=command.observaciones,
                    status="Aprobado",
                    approved_by=user_id,
                    approved_at=modified_at,
                    updated_at=modified_at,
                )
                .returning(*pedido_sugerido.c)
            ).mappings().one()
            updated_items.append(dict(updated))

        return SuggestedOrderBatchData(
            batch_id=batch_id,
            updated_at=modified_at,
            items=updated_items,
        )

    def get_by_location(
        self,
        location: int,
        page: int,
        page_size: int,
        forecast_origin: date | None = None,
    ) -> SuggestedOrderPageData:
        rows = (
            self.db.execute(
                build_suggested_orders_page_query(
                    location,
                    page,
                    page_size,
                    forecast_origin,
                )
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

    def get_history(
        self,
        key: SuggestedOrderKey,
        page: int,
        page_size: int,
    ) -> SuggestedOrderHistoryPageData:
        condition = and_(
            pedido_sugerido_historial.c.item == key.item,
            pedido_sugerido_historial.c.location == key.location,
            pedido_sugerido_historial.c.forecast_origin == key.forecast_origin,
            pedido_sugerido_historial.c.horizon_day == key.horizon_day,
        )
        total_items = self.db.scalar(
            select(func.count())
            .select_from(pedido_sugerido_historial)
            .where(condition)
        )
        items = (
            self.db.execute(
                select(*pedido_sugerido_historial.c)
                .where(condition)
                .order_by(
                    pedido_sugerido_historial.c.modified_at.desc(),
                    pedido_sugerido_historial.c.change_id.desc(),
                )
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .mappings()
            .all()
        )
        return SuggestedOrderHistoryPageData(
            total_items=max(total_items or 0, 0),
            items=[dict(item) for item in items],
        )
