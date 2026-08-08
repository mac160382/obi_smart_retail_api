import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.forecast_csv_parser import (
    ParsedForecastCSV,
    parse_forecast_csv,
)
from app.modules.imports.service import ImportService

COLUMNS = [
    "forecast_origin",
    "target_date",
    "horizon_day",
    "descripcion_item",
    "item",
    "item_code",
    "descripcion_tienda",
    "location",
    "location_code",
    "forecast_qty_vendida",
    "raw_prediction",
    "was_clipped_to_zero",
    "unknown_item",
    "unknown_location",
    "history_days",
    "model_key",
    "model_name",
    "model_cutoff",
    "generated_utc",
]

VALID_VALUES = [
    "2026-06-23",
    "2026-06-24",
    "1",
    "",
    "AUSP20S",
    "1",
    "",
    "13",
    "3",
    "0.3941360270552669",
    "0.3941360270552669",
    "False",
    "False",
    "False",
    "265",
    "random_forest_global",
    "Random Forest global",
    "2026-06-22",
    "2026-08-08T01:11:25.026786+00:00",
]


def make_upload(values: list[str]) -> MagicMock:
    content = ",".join(COLUMNS) + "\n" + ",".join(values) + "\n"
    upload = MagicMock()
    upload.filename = "Pronostico_template.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[content.encode("utf-8"), b""])
    return upload


def test_forecast_parser_converts_template_values() -> None:
    parsed = asyncio.run(parse_forecast_csv(make_upload(VALID_VALUES)))
    row = parsed.rows[0]

    assert row["forecast_origin"] == date(2026, 6, 23)
    assert row["target_date"] == date(2026, 6, 24)
    assert row["horizon_day"] == 1
    assert row["descripcion_item"] is None
    assert row["item"] == "AUSP20S"
    assert row["forecast_qty_vendida"] == 0.3941360270552669
    assert row["was_clipped_to_zero"] is False
    assert row["generated_utc"] == datetime(
        2026,
        8,
        8,
        1,
        11,
        25,
        26786,
        tzinfo=timezone.utc,
    )


def test_forecast_parser_rejects_entire_file_for_timestamp_without_zone() -> None:
    values = VALID_VALUES.copy()
    values[COLUMNS.index("generated_utc")] = "2026-08-08T01:11:25"

    try:
        asyncio.run(parse_forecast_csv(make_upload(values)))
    except CSVValidationError as exc:
        assert "1 fila(s) inválida(s)" in str(exc)
        assert "sin zona horaria" in str(exc)
    else:
        raise AssertionError("El parser aceptó generated_utc sin zona horaria")


def test_forecast_service_replaces_only_forecast_then_commits() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.add_job.side_effect = lambda _job: events.append("job")
    service.repository.replace_forecast.side_effect = (
        lambda *_args, **_kwargs: events.append("replace_forecast") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")
    parsed = ParsedForecastCSV(
        filename="Pronostico_template.csv",
        columns=COLUMNS,
        rows=[{"item": "AUSP20S"}],
    )

    with (
        patch(
            "app.modules.imports.service.parse_forecast_csv",
            new=AsyncMock(return_value=parsed),
        ),
        patch(
            "app.modules.suggested_orders.service."
            "SuggestedOrderService.recalculate"
        ) as recalculate,
    ):
        job = asyncio.run(service.import_forecast(uuid4(), MagicMock()))

    assert events == ["job", "replace_forecast", "commit"]
    assert job.destination_schema == "public"
    assert job.destination_table == "pronostico"
    recalculate.assert_not_called()
    db.rollback.assert_not_called()


def test_forecast_service_rolls_back_if_replace_fails() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.replace_forecast.side_effect = RuntimeError(
        "database error"
    )
    parsed = ParsedForecastCSV(
        filename="Pronostico_template.csv",
        columns=COLUMNS,
        rows=[{"item": "AUSP20S"}],
    )

    with patch(
        "app.modules.imports.service.parse_forecast_csv",
        new=AsyncMock(return_value=parsed),
    ):
        try:
            asyncio.run(service.import_forecast(uuid4(), MagicMock()))
        except RuntimeError:
            pass
        else:
            raise AssertionError("El servicio ocultó el error del repositorio")

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
