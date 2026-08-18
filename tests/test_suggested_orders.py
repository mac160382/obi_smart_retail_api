from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.main import create_app
from app.modules.imports.models import (
    pedido_sugerido,
    pedido_sugerido_historial,
)
from app.modules.suggested_orders.events import StoredSSEEvent
from app.modules.suggested_orders.repository import (
    ReplacementCounts,
    SuggestedOrderAlreadyApprovedError,
    SuggestedOrderBatchData,
    SuggestedOrderCalculationInProgressError,
    SuggestedOrderKey,
    SuggestedOrderPageData,
    SuggestedOrderRepository,
    SuggestedOrderUpdateCommand,
    build_suggested_orders_insert,
    build_suggested_orders_page_query,
)
from app.modules.suggested_orders.schemas import (
    SuggestedOrderBatchUpdateRequest,
)
from app.modules.suggested_orders.service import SuggestedOrderService


def test_forecast_fields_are_required_in_suggested_orders() -> None:
    assert pedido_sugerido.c.forecast_origin.nullable is False
    assert pedido_sugerido.c.horizon_day.nullable is False
    assert pedido_sugerido.c.target_date.nullable is False


def test_approval_columns_and_logical_unique_key_are_defined() -> None:
    assert "observaciones" in pedido_sugerido.c
    assert "approved_by" in pedido_sugerido.c
    assert "approved_at" in pedido_sugerido.c
    assert "updated_at" in pedido_sugerido.c
    unique_keys = {
        tuple(column.name for column in constraint.columns)
        for constraint in pedido_sugerido.constraints
        if constraint.name == "uq_pedido_sugerido_logical_key"
    }
    assert unique_keys == {
        ("item", "location", "forecast_origin", "horizon_day")
    }
    assert "batch_id" in pedido_sugerido_historial.c
    assert "modified_by" in pedido_sugerido_historial.c


def test_batch_and_history_routes_require_oauth2() -> None:
    paths = create_app().openapi()["paths"]

    assert paths["/api/v1/suggested-orders/batch"]["patch"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]
    assert paths["/api/v1/suggested-orders/history"]["get"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]


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
    assert "WHERE NOT (EXISTS" in sql
    assert "approved_orders.status = 'Aprobado'" in sql


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


def test_page_query_filters_by_forecast_origin_when_provided() -> None:
    sql = str(
        build_suggested_orders_page_query(
            location=13,
            page=1,
            page_size=50,
            forecast_origin=date(2026, 8, 16),
        ).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "public.pedido_sugerido.location = 13" in sql
    assert "public.pedido_sugerido.horizon_day = 1" in sql
    assert "public.pedido_sugerido.forecast_origin = '2026-08-16'" in sql


def test_repository_replaces_rows_after_acquiring_lock() -> None:
    db = MagicMock()
    db.scalar.return_value = True
    deleted_result = MagicMock(rowcount=4)
    inserted_result = MagicMock(rowcount=8)
    db.execute.side_effect = [deleted_result, inserted_result]

    counts = SuggestedOrderRepository(db).replace_suggested_orders()

    assert counts == ReplacementCounts(deleted_rows=4, inserted_rows=8)
    assert db.scalar.call_count == 1
    assert db.execute.call_count == 2
    delete_sql = str(
        db.execute.call_args_list[0].args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "public.pedido_sugerido.status != 'Aprobado'" in delete_sql


def test_repository_rejects_concurrent_calculation() -> None:
    db = MagicMock()
    db.scalar.return_value = False

    with pytest.raises(SuggestedOrderCalculationInProgressError):
        SuggestedOrderRepository(db).replace_suggested_orders()

    db.execute.assert_not_called()


def test_repository_approves_batch_and_writes_history() -> None:
    db = MagicMock()
    db.scalar.return_value = True
    current = {
        "item": "ITEM-1",
        "location": 13,
        "forecast_origin": date(2026, 8, 16),
        "horizon_day": 1,
        "target_date": date(2026, 8, 17),
        "ajustado": None,
        "observaciones": None,
        "status": "Estimado",
    }
    updated = {
        **current,
        "ajustado": 25.5,
        "observaciones": "Ajuste por demanda",
        "status": "Aprobado",
    }
    select_result = MagicMock()
    select_result.mappings.return_value.one_or_none.return_value = current
    update_result = MagicMock()
    update_result.mappings.return_value.one.return_value = updated
    db.execute.side_effect = [select_result, MagicMock(), update_result]
    command = SuggestedOrderUpdateCommand(
        key=SuggestedOrderKey(
            item="ITEM-1",
            location=13,
            forecast_origin=date(2026, 8, 16),
        ),
        ajustado=25.5,
        observaciones="Ajuste por demanda",
    )
    user_id = uuid4()
    batch_id = uuid4()
    modified_at = datetime(2026, 8, 17, tzinfo=UTC)

    result = SuggestedOrderRepository(db).approve_batch(
        [command],
        user_id,
        batch_id,
        modified_at,
    )

    assert result.batch_id == batch_id
    assert result.items[0]["status"] == "Aprobado"
    history_values = db.execute.call_args_list[1].args[1][0]
    assert history_values["ajustado_anterior"] is None
    assert history_values["ajustado_nuevo"] == 25.5
    assert history_values["status_anterior"] == "Estimado"
    assert history_values["status_nuevo"] == "Aprobado"
    assert history_values["modified_by"] == user_id


def test_repository_rejects_already_approved_order() -> None:
    db = MagicMock()
    db.scalar.return_value = True
    select_result = MagicMock()
    select_result.mappings.return_value.one_or_none.return_value = {
        "status": "Aprobado"
    }
    db.execute.return_value = select_result
    command = SuggestedOrderUpdateCommand(
        key=SuggestedOrderKey(
            item="ITEM-1",
            location=13,
            forecast_origin=date(2026, 8, 16),
        ),
        ajustado=25.5,
        observaciones="No debe modificarse",
    )

    with pytest.raises(SuggestedOrderAlreadyApprovedError):
        SuggestedOrderRepository(db).approve_batch(
            [command],
            uuid4(),
            uuid4(),
            datetime(2026, 8, 17, tzinfo=UTC),
        )

    assert db.execute.call_count == 1


def test_batch_schema_rejects_duplicate_logical_keys() -> None:
    item = {
        "item": "ITEM-1",
        "location": 13,
        "forecast_origin": "2026-08-16",
        "ajustado": 25.5,
        "observaciones": "Ajuste por demanda",
    }

    with pytest.raises(ValidationError):
        SuggestedOrderBatchUpdateRequest.model_validate(
            {"items": [item, item]}
        )


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
            "observaciones": None,
            "approved_by": None,
            "approved_at": None,
            "updated_at": None,
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


def test_service_commits_successful_batch_approval() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    command = SuggestedOrderUpdateCommand(
        key=SuggestedOrderKey(
            item="ITEM-1",
            location=13,
            forecast_origin=date(2026, 8, 16),
        ),
        ajustado=25.5,
        observaciones="Ajuste por demanda",
    )
    expected = SuggestedOrderBatchData(
        batch_id=uuid4(),
        updated_at=datetime(2026, 8, 17, tzinfo=UTC),
        items=[{"item": "ITEM-1"}],
    )
    service.repository.approve_batch.return_value = expected

    result = service.approve_batch(uuid4(), [command])

    assert result is expected
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_service_rolls_back_failed_batch_approval() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    service.repository.approve_batch.side_effect = (
        SuggestedOrderAlreadyApprovedError(
            SuggestedOrderKey(
                item="ITEM-1",
                location=13,
                forecast_origin=date(2026, 8, 16),
            )
        )
    )

    with pytest.raises(SuggestedOrderAlreadyApprovedError):
        service.approve_batch(uuid4(), [])

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_service_persists_forecast_notification_in_recalculation_transaction() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    service.repository.replace_suggested_orders.return_value = ReplacementCounts(
        deleted_rows=4,
        inserted_rows=8,
    )
    source_event_id = uuid4()
    notification = MagicMock(spec=StoredSSEEvent)
    calls: list[str] = []
    db.commit.side_effect = lambda: calls.append("commit")

    with patch(
        "app.modules.suggested_orders.service.SuggestedOrderEventRepository"
    ) as event_repository_class:
        event_repository = event_repository_class.return_value
        event_repository.find_by_source_event_id.return_value = None
        event_repository.create.side_effect = (
            lambda **_kwargs: calls.append("notification") or notification
        )
        result = service.recalculate(
            source_event_id,
            source_event_id=source_event_id,
            correlation_id="forecast-import-123",
            forecast_origin=date(2026, 8, 11),
        )

    assert calls == ["notification", "commit"]
    assert result.notification is notification
    payload = event_repository.create.call_args.kwargs["payload"]
    assert payload["status"] == "completed"
    assert payload["forecast_event_id"] == str(source_event_id)
    assert payload["forecast_origin"] == "2026-08-11"
    assert payload["correlation_id"] == "forecast-import-123"


def test_service_does_not_recalculate_an_already_processed_forecast_event() -> None:
    db = MagicMock()
    service = SuggestedOrderService(db)
    service.repository = MagicMock()
    source_event_id = uuid4()
    existing = StoredSSEEvent(
        id=7,
        event_id=uuid4(),
        event_type="suggested-orders.recalculated",
        payload={
            "destination": "public.pedido_sugerido",
            "deleted_rows": 4,
            "inserted_rows": 8,
            "calculated_at": "2026-08-11T12:00:00+00:00",
            "duration_ms": 250,
        },
        created_at=datetime(2026, 8, 11, tzinfo=UTC),
    )

    with patch(
        "app.modules.suggested_orders.service.SuggestedOrderEventRepository"
    ) as event_repository_class:
        event_repository_class.return_value.find_by_source_event_id.return_value = (
            existing
        )
        result = service.recalculate(
            source_event_id,
            source_event_id=source_event_id,
        )

    assert result.notification == existing
    service.repository.replace_suggested_orders.assert_not_called()
    db.commit.assert_not_called()


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
