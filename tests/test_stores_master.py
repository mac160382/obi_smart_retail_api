import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.service import ImportService
from app.modules.imports.stores_csv_parser import (
    ParsedStoresMasterCSV,
    parse_stores_master_csv,
)

COLUMNS = [
    "location",
    "descripcion",
    "tipo_centro",
    "region",
    "estado",
    "sociedad",
]

VALID_VALUES = [
    "101",
    "Tienda Centro",
    "Supermercado",
    "Norte",
    "1",
    "10",
]


def make_upload(values: list[str]) -> MagicMock:
    content = ",".join(COLUMNS) + "\n" + ",".join(values) + "\n"
    upload = MagicMock()
    upload.filename = "maestro_tiendas.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[content.encode("utf-8"), b""])
    return upload


def test_stores_parser_converts_supported_types() -> None:
    parsed = asyncio.run(parse_stores_master_csv(make_upload(VALID_VALUES)))

    assert parsed.rows[0]["location"] == 101
    assert parsed.rows[0]["descripcion"] == "Tienda Centro"
    assert parsed.rows[0]["estado"] == 1
    assert parsed.rows[0]["sociedad"] == 10


def test_stores_parser_rejects_entire_file_for_invalid_integer() -> None:
    values = VALID_VALUES.copy()
    values[COLUMNS.index("location")] = "ABC"

    try:
        asyncio.run(parse_stores_master_csv(make_upload(values)))
    except CSVValidationError as exc:
        assert "1 fila(s) inválida(s)" in str(exc)
    else:
        raise AssertionError("El parser aceptó un entero inválido")


def test_stores_service_replaces_then_commits() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.add_job.side_effect = lambda _job: events.append("job")
    service.repository.replace_stores_master.side_effect = (
        lambda *_args, **_kwargs: events.append("replace") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")
    parsed = ParsedStoresMasterCSV(
        filename="maestro_tiendas.csv",
        columns=COLUMNS,
        rows=[{"location": 101}],
    )

    with patch(
        "app.modules.imports.service.parse_stores_master_csv",
        new=AsyncMock(return_value=parsed),
    ):
        job = asyncio.run(
            service.import_stores_master(uuid4(), MagicMock())
        )

    assert events == ["job", "replace", "commit"]
    assert job.destination_schema == "public"
    assert job.destination_table == "lacteos_maestro_tiendas"
    db.rollback.assert_not_called()


def test_stores_service_rolls_back_if_replace_fails() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.replace_stores_master.side_effect = RuntimeError(
        "database error"
    )
    parsed = ParsedStoresMasterCSV(
        filename="maestro_tiendas.csv",
        columns=COLUMNS,
        rows=[{"location": 101}],
    )

    with patch(
        "app.modules.imports.service.parse_stores_master_csv",
        new=AsyncMock(return_value=parsed),
    ):
        try:
            asyncio.run(
                service.import_stores_master(uuid4(), MagicMock())
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("El servicio ocultó el error del repositorio")

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
