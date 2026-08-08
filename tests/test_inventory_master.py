import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.inventory_csv_parser import (
    ParsedInventoryMasterCSV,
    parse_inventory_master_csv,
)
from app.modules.imports.service import ImportService

COLUMNS = [
    "item_code",
    "description_item_code",
    "proveedor_code",
    "description_proveedor",
    "macrofamily_code",
    "description_macrofamily_code",
    "familia_code",
    "description_familia",
    "description_subagrupacion",
    "location_code",
    "description_location_code",
    "item_type",
    "estado_articulo",
    "temporal_freeattr5",
    "control_type",
    "estado_planificacion",
    "logistic_class_code",
    "abc_cadena",
    "service_level",
    "frecuencia_pedido",
    "minimum_handling_quantity_units",
    "lead_time_days",
    "review_period_days",
    "current_stock_units",
    "expected_demand_qty_period_direct_sales_units_day",
    "cobertura",
    "on_order_in_transit_units",
    "extra_visibilidad_units",
    "item_birth_day_date",
    "overstock_units",
    "cantidad_ultimo_ingreso",
    "fecha_ultimo_ingreso",
]

VALID_VALUES = [
    "A1", "Leche", "P1", "Proveedor", "M1", "Macro", "F1", "Familia",
    "Subgrupo", "L1", "Tienda", "TYPE", "ACTIVE", "X", "C", "P", "L",
    "A", "0.9500", "WEEKLY", "1.0000", "2", "7", "10.0000", "2.5000",
    "4.0000", "3.0000", "1", "2020-01-01", "0", "5.0000", "2026-07-01",
]


def make_upload(values: list[str]) -> MagicMock:
    content = ",".join(COLUMNS) + "\n" + ",".join(values) + "\n"
    upload = MagicMock()
    upload.filename = "inventario.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[content.encode("utf-8"), b""])
    return upload


def test_inventory_parser_converts_supported_types() -> None:
    parsed = asyncio.run(parse_inventory_master_csv(make_upload(VALID_VALUES)))

    assert parsed.rows[0]["service_level"] == Decimal("0.9500")
    assert parsed.rows[0]["lead_time_days"] == 2
    assert parsed.rows[0]["fecha_ultimo_ingreso"] == date(2026, 7, 1)


def test_inventory_parser_rejects_entire_file_for_invalid_numeric() -> None:
    values = VALID_VALUES.copy()
    values[COLUMNS.index("service_level")] = "0.12345"

    try:
        asyncio.run(parse_inventory_master_csv(make_upload(values)))
    except CSVValidationError as exc:
        assert "1 fila(s) inválida(s)" in str(exc)
    else:
        raise AssertionError("El parser aceptó un NUMERIC(18,4) inválido")


def test_inventory_service_replaces_then_commits() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.add_job.side_effect = lambda _job: events.append("job")
    service.repository.replace_inventory_master.side_effect = (
        lambda *_args, **_kwargs: events.append("replace") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")
    parsed = ParsedInventoryMasterCSV(
        filename="inventario.csv",
        columns=COLUMNS,
        rows=[{"item_code": "A1"}],
    )

    with patch(
        "app.modules.imports.service.parse_inventory_master_csv",
        new=AsyncMock(return_value=parsed),
    ):
        job = asyncio.run(
            service.import_inventory_master(uuid4(), MagicMock())
        )

    assert events == ["job", "replace", "commit"]
    assert job.destination_schema == "public"
    assert job.destination_table == "g2_maestro_inventario_lacteos"
    db.rollback.assert_not_called()
