import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.items_csv_parser import (
    ParsedItemsMasterCSV,
    parse_items_master_csv,
)
from app.modules.imports.service import ImportService

COLUMNS = [
    "item",
    "descripcion",
    "itemtype",
    "desc_itemtype",
    "munit",
    "unitcost",
    "listprice",
    "servclas",
    "desc_servclas",
    "vida_util",
    "division_cod",
    "division_desc",
    "macrofam_cod",
    "macrofam_desc",
    "familia_cod",
    "familia_desc",
    "subfamilia_cod",
    "subfamilia_desc",
    "cod_jerarq_nivel3",
    "des_jerar_nivel3",
    "cod_jerarq_nivel4",
    "des_jerar_nivel4",
    "cod_jerarq_nivel5",
    "des_jerar_nivel5",
    "cod_jerarq_nivel6",
    "des_jerar_nivel6",
]

VALID_VALUES = [
    "A1",
    "Leche entera",
    "1",
    "Producto",
    "UN",
    "10.2500",
    "12.5000",
    "2",
    "Refrigerado",
    "30.50",
    "10",
    "Lácteos",
    "20",
    "Leches",
    "30",
    "Leche líquida",
    "40",
    "Entera",
    "300",
    "Nivel 3",
    "400",
    "Nivel 4",
    "500",
    "Nivel 5",
    "600",
    "Nivel 6",
]


def make_upload(values: list[str]) -> MagicMock:
    content = ",".join(COLUMNS) + "\n" + ",".join(values) + "\n"
    upload = MagicMock()
    upload.filename = "maestro_items.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[content.encode("utf-8"), b""])
    return upload


def test_items_parser_converts_supported_types() -> None:
    parsed = asyncio.run(parse_items_master_csv(make_upload(VALID_VALUES)))

    assert parsed.rows[0]["itemtype"] == 1
    assert parsed.rows[0]["unitcost"] == Decimal("10.2500")
    assert parsed.rows[0]["vida_util"] == Decimal("30.50")
    assert parsed.rows[0]["cod_jerarq_nivel6"] == Decimal("600")


def test_items_parser_rejects_entire_file_for_invalid_numeric() -> None:
    values = VALID_VALUES.copy()
    values[COLUMNS.index("unitcost")] = "10.12345"

    try:
        asyncio.run(parse_items_master_csv(make_upload(values)))
    except CSVValidationError as exc:
        assert "1 fila(s) inválida(s)" in str(exc)
    else:
        raise AssertionError("El parser aceptó un NUMERIC(14,4) inválido")


def test_items_service_replaces_then_commits() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.add_job.side_effect = lambda _job: events.append("job")
    service.repository.replace_items_master.side_effect = (
        lambda *_args, **_kwargs: events.append("replace") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")
    parsed = ParsedItemsMasterCSV(
        filename="maestro_items.csv",
        columns=COLUMNS,
        rows=[{"item": "A1"}],
    )

    with patch(
        "app.modules.imports.service.parse_items_master_csv",
        new=AsyncMock(return_value=parsed),
    ):
        job = asyncio.run(
            service.import_items_master(uuid4(), MagicMock())
        )

    assert events == ["job", "replace", "commit"]
    assert job.destination_schema == "public"
    assert job.destination_table == "lacteos_maestro_items"
    db.rollback.assert_not_called()


def test_items_service_rolls_back_if_replace_fails() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.replace_items_master.side_effect = RuntimeError(
        "database error"
    )
    parsed = ParsedItemsMasterCSV(
        filename="maestro_items.csv",
        columns=COLUMNS,
        rows=[{"item": "A1"}],
    )

    with patch(
        "app.modules.imports.service.parse_items_master_csv",
        new=AsyncMock(return_value=parsed),
    ):
        try:
            asyncio.run(
                service.import_items_master(uuid4(), MagicMock())
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("El servicio ocultó el error del repositorio")

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
