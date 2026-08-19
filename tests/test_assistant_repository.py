from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.modules.assistant.repository import AssistantQueryRepository


def test_forecast_repository_applies_filters_and_pagination() -> None:
    db = MagicMock()
    db.scalar.return_value = 3
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "item": "A",
            "location": 13,
            "forecast_origin": date(2026, 8, 16),
            "target_date": date(2026, 8, 18),
            "horizon_day": 2,
            "forecast_qty_vendida": 8.5,
        }
    ]
    settings = Settings.model_construct(
        forecast_schema="public",
        forecast_table="pronostico",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_forecasts(
        item="A",
        item_code=101,
        location=13,
        location_code=13,
        forecast_origin=date(2026, 8, 16),
        target_date_from=date(2026, 8, 17),
        target_date_to=date(2026, 8, 23),
        horizon_day=2,
        offset=1,
        limit=1,
    )

    count_query = str(db.scalar.call_args.args[0])
    data_query = str(db.execute.call_args.args[0])
    assert "pronostico.item" in count_query
    assert "pronostico.forecast_origin" in count_query
    assert data_query.lstrip().startswith("SELECT")
    assert result["meta"]["source"] == "public.pronostico"
    assert result["meta"]["records_returned"] == 1
    assert result["meta"]["total_matching"] == 3
    assert result["meta"]["has_more"] is True
    assert result["data"][0]["forecast_qty_vendida"] == 8.5


@pytest.mark.parametrize(
    ("aggregation", "expected_sql"),
    [
        ("detail", "ORDER BY"),
        ("day", "GROUP BY"),
        ("week", "date_trunc"),
    ],
)
def test_sales_repository_supports_each_aggregation(
    aggregation: str,
    expected_sql: str,
) -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item": "A", "location": 13, "qty_vendida": 12}
    ]
    settings = Settings.model_construct(
        database_schema="public",
        historical_sales_table="lacteos_ventas_historicas",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_sales(
        item="A",
        location=13,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 7),
        aggregation=aggregation,
        limit=10,
    )

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert expected_sql in query
    assert "lacteos_ventas_historicas.fecha" in query
    assert result["meta"]["source"] == "public.lacteos_ventas_historicas"
    assert result["meta"]["aggregation"] == aggregation
    assert result["meta"]["records_returned"] == 1


def test_items_repository_applies_catalog_filters() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item": "A", "descripcion": "Leche", "itemtype": 1, "familia_cod": 10}
    ]
    settings = Settings.model_construct(
        items_master_schema="public",
        items_master_table="lacteos_maestro_items",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_items(
        item="A",
        descripcion="Leche",
        itemtype=1,
        familia_cod=10,
        limit=5,
    )

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert "lacteos_maestro_items.descripcion" in query
    assert "lower(" in query
    assert result["meta"]["endpoint"] == "/api/v1/items"
    assert result["meta"]["source"] == "public.lacteos_maestro_items"
    assert result["meta"]["records_returned"] == 1


def test_stores_repository_applies_catalog_filters() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"location": 13, "descripcion": "Centro", "region": "Norte"}
    ]
    settings = Settings.model_construct(
        stores_master_schema="public",
        stores_master_table="lacteos_maestro_tiendas",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_stores(
        location=13,
        descripcion="Centro",
        tipo_centro="Tienda",
        region="Norte",
        estado=1,
        limit=5,
    )

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert "lacteos_maestro_tiendas.location" in query
    assert "lacteos_maestro_tiendas.region" in query
    assert result["meta"]["endpoint"] == "/api/v1/stores"
    assert result["meta"]["source"] == "public.lacteos_maestro_tiendas"


def test_inventory_repository_applies_operational_filters() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item_code": "A", "location_code": "13", "current_stock_units": 8}
    ]
    settings = Settings.model_construct(
        inventory_master_schema="public",
        inventory_master_table="g2_maestro_inventario_lacteos",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_inventory(
        item_code="A",
        location_code="13",
        proveedor_code="P1",
        estado_articulo="Activo",
        limit=5,
    )

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert "g2_maestro_inventario_lacteos.item_code" in query
    assert "g2_maestro_inventario_lacteos.proveedor_code" in query
    assert result["meta"]["endpoint"] == "/api/v1/inventory"
    assert result["meta"]["source"] == "public.g2_maestro_inventario_lacteos"


def test_promotions_repository_filters_active_date() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"item": "A", "event_code": "PROMO-1", "status": "Activa"}
    ]
    settings = Settings.model_construct(
        current_promotions_schema="public",
        current_promotions_table="g2_lacteos_promociones_vigentes",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_promotions(
        item="A",
        event_code="PROMO-1",
        status="Activa",
        active_on=date(2026, 8, 18),
        limit=5,
    )

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert "g2_lacteos_promociones_vigentes.inicio" in query
    assert "g2_lacteos_promociones_vigentes.fin" in query
    assert result["meta"]["endpoint"] == "/api/v1/promotions"
    assert result["meta"]["source"] == "public.g2_lacteos_promociones_vigentes"


def test_parameters_repository_uses_inventory_operational_fields() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "item": "A",
            "location": "13",
            "supplier": "101",
            "lead_time_days": 2,
            "review_period_days": 7,
        }
    ]
    settings = Settings.model_construct(
        inventory_master_schema="public",
        inventory_master_table="g2_maestro_inventario_lacteos",
    )
    repository = AssistantQueryRepository(db, settings)

    result = repository.get_parameters(item="A", location=13, supplier=101, limit=5)

    query = str(db.execute.call_args.args[0])
    assert query.lstrip().startswith("SELECT")
    assert "g2_maestro_inventario_lacteos.lead_time_days" in query
    assert "g2_maestro_inventario_lacteos.review_period_days" in query
    assert "g2_maestro_inventario_lacteos.minimum_handling_quantity_units" in query
    assert result["meta"]["endpoint"] == "/api/v1/parameters"
    assert result["meta"]["source"] == "public.g2_maestro_inventario_lacteos"
    assert result["meta"]["records_returned"] == 1


def test_executions_repository_reads_manifest_and_filters_phase(tmp_path: Path) -> None:
    (tmp_path / "execution_manifest.json").write_text(
        """[
          {"phase":"13.1","process":"Inventario","filename":"phase13_1.txt"},
          {"phase":"13.2","process":"Validación","filename":"missing.txt"}
        ]""",
        encoding="utf-8",
    )
    (tmp_path / "phase13_1.txt").write_text(
        "Status: SUCCESS\nInicio UTC: 2026-08-18T10:00:00Z\nFin UTC: 2026-08-18T10:01:00Z\n",
        encoding="utf-8",
    )
    settings = Settings.model_construct(assistant_execution_dir=tmp_path)
    repository = AssistantQueryRepository(MagicMock(), settings)

    result = repository.get_executions(phase="13.1")

    assert result["meta"]["endpoint"] == "/api/v1/executions"
    assert result["meta"]["source"] == ["phase13_1.txt", "missing.txt"]
    assert result["meta"]["records_returned"] == 1
    assert result["data"][0]["available"] is True
    assert result["data"][0]["status"] == "SUCCESS"
    assert result["data"][0]["started"] == "2026-08-18T10:00:00Z"


def test_executions_repository_reports_missing_result_file(tmp_path: Path) -> None:
    (tmp_path / "execution_manifest.json").write_text(
        '[{"phase":"13.2","process":"Validación","filename":"missing.txt"}]',
        encoding="utf-8",
    )
    settings = Settings.model_construct(assistant_execution_dir=tmp_path)
    repository = AssistantQueryRepository(MagicMock(), settings)

    result = repository.get_executions()

    assert result["meta"]["records_returned"] == 1
    assert result["data"][0] == {
        "phase": "13.2",
        "process": "Validación",
        "source_file": "missing.txt",
        "available": False,
        "status": None,
    }
