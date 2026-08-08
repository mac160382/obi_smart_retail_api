from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.imports.models import pedido_sugerido
from app.modules.suggested_orders.repository import (
    ReplacementCounts,
    SuggestedOrderCalculationInProgressError,
    SuggestedOrderPageData,
    SuggestedOrderRepository,
    build_suggested_orders_insert,
    build_suggested_orders_page_query,
)
from app.modules.suggested_orders.service import SuggestedOrderService


def test_forecast_fields_are_required_in_suggested_orders() -> None:
    assert pedido_sugerido.c.forecast_origin.nullable is False
    assert pedido_sugerido.c.horizon_day.nullable is False
    assert pedido_sugerido.c.target_date.nullable is False


def test_insert_statement_uses_ctes_and_qualified_tables() -> None:
    sql = str(
        build_suggested_orders_insert().compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "WITH ultima_fecha AS" in sql
    assert "max(public.pronostico.forecast_origin)" in sql
    assert "INSERT INTO public.pedido_sugerido" in sql
    assert "item, location, descripcion_tienda, descripcion_item" in sql
    assert "status, forecast_origin, horizon_day, target_date" in sql
    assert "FROM public.g2_maestro_inventario_lacteos" in sql
    assert "LEFT OUTER JOIN public.pronostico" in sql
    assert "LEFT OUTER JOIN public.vst_promociones_vigentes" in sql
    assert "JOIN ultima_fecha ON true" in sql
    assert "coalesce(public.pronostico.forecast_qty_vendida, 0)" in sql
    assert (
        "1 - coalesce(public.vst_promociones_vigentes.uplift_esperado, 0)"
        in sql
    )
    assert "- coalesce(public.g2_maestro_inventario_lacteos." in sql
    assert "coalesce(public.pronostico.forecast_origin, ultima_fecha.forecast_origin)" in sql
    assert "coalesce(public.pronostico.horizon_day, 1)" in sql
    assert "coalesce(public.pronostico.target_date, ultima_fecha.forecast_origin)" in sql
    assert "LATERAL" not in sql
    assert "ceil(" in sql
    assert "description_item_code" in sql
    assert "description_proveedor" in sql
    assert "'Estimado'" in sql


def test_page_query_filters_orders_and_applies_pagination() -> None:
    sql = str(
        build_suggested_orders_page_query(
            location=13,
            page=2,
            page_size=25,
        ).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "WITH filtered_orders AS" in sql
    assert "public.pedido_sugerido.location = 13" in sql
    assert "public.pedido_sugerido.horizon_day = 1" in sql
    assert "ORDER BY filtered_orders.item" in sql
    assert "LIMIT 25 OFFSET 25" in sql


def test_repository_replaces_rows_after_acquiring_lock() -> None:
    db = MagicMock()
    db.scalar.side_effect = [True, 8]
    deleted_result = MagicMock(rowcount=4)
    db.execute.side_effect = [deleted_result, MagicMock()]

    counts = SuggestedOrderRepository(db).replace_suggested_orders()

    assert counts == ReplacementCounts(deleted_rows=4, inserted_rows=8)
    assert db.scalar.call_count == 2
    assert db.execute.call_count == 2


def test_repository_rejects_concurrent_calculation() -> None:
    db = MagicMock()
    db.scalar.return_value = False

    with pytest.raises(SuggestedOrderCalculationInProgressError):
        SuggestedOrderRepository(db).replace_suggested_orders()

    db.execute.assert_not_called()


def test_repository_returns_page_and_total_from_one_query() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "total_items": 3,
            "item": "ITEM-1",
            "forecast_origin": date(2026, 6, 23),
            "horizon_day": 1,
            "target_date": date(2026, 6, 24),
            "location": 13,
            "descripcion_tienda": "Tienda 13",
            "descripcion_item": "Producto de prueba",
            "descripcion_proveedor": "Proveedor de prueba",
            "prediccion": 10.5,
            "ajustado": None,
            "lead_time_days": 2,
            "review_period_days": 7,
            "uplift_esperado": 0.1,
            "minimum_handling_quantity_units": 5,
            "current_stock_units": 3,
            "on_order_in_transit_units": 1,
            "sugerido": 13,
            "status": "Estimado",
        }
    ]

    result = SuggestedOrderRepository(db).get_by_location(13, 1, 1)

    assert result.total_items == 3
    assert result.items[0]["item"] == "ITEM-1"
    assert "total_items" not in result.items[0]
    db.execute.assert_called_once()


def test_service_commits_successful_replacement() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    service.repository.replace_suggested_orders.return_value = ReplacementCounts(
        deleted_rows=4,
        inserted_rows=8,
    )

    result = service.recalculate(uuid4())

    assert result.destination == "public.pedido_sugerido"
    assert result.deleted_rows == 4
    assert result.inserted_rows == 8
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_service_rolls_back_failed_replacement() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    service.repository.replace_suggested_orders.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        service.recalculate(uuid4())

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_service_calculates_page_metadata() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    service.repository.get_by_location.return_value = SuggestedOrderPageData(
        total_items=101,
        items=[],
    )

    result = service.get_by_location(location=13, page=2, page_size=50)

    assert result.location == 13
    assert result.page == 2
    assert result.page_size == 50
    assert result.total_items == 101
    assert result.total_pages == 3
