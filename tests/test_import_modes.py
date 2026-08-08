import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import BackgroundTasks

from app.modules.imports.csv_parser import ParsedCSV
from app.modules.imports.models import ImportStatus
from app.modules.imports.router import upload_historical_sales_csv
from app.modules.imports.schemas import ImportMode
from app.modules.imports.service import ImportResult, ImportService


def make_parsed_csv() -> ParsedCSV:
    return ParsedCSV(
        filename="ventas.csv",
        columns=["fecha", "item"],
        rows=[{"fecha": None, "item": "A"}],
        rejected_rows=0,
        errors=[],
    )


def make_job() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        original_filename="ventas.csv",
        destination_schema="public",
        destination_table="lacteos_ventas_historicas",
        status=ImportStatus.COMPLETED,
        total_rows=1,
        inserted_rows=1,
        rejected_rows=0,
        columns={"names": ["fecha", "item"], "validation_errors": []},
    )


def test_incremental_commits_and_returns_rows_for_feature_engineering() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.bulk_insert_historical_sales.side_effect = (
        lambda *_args, **_kwargs: events.append("insert") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")

    parsed = make_parsed_csv()
    with patch(
        "app.modules.imports.service.parse_csv",
        new=AsyncMock(return_value=parsed),
    ):
        result = asyncio.run(
            service.import_csv(uuid4(), MagicMock(), ImportMode.INCREMENTAL)
        )

    assert events == ["insert", "commit"]
    service.repository.delete_historical_sales.assert_not_called()
    assert result.feature_engineering_rows is parsed.rows


def test_replace_deletes_then_inserts_in_same_transaction() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.delete_historical_sales.side_effect = (
        lambda: events.append("delete")
    )
    service.repository.bulk_insert_historical_sales.side_effect = (
        lambda *_args, **_kwargs: events.append("insert") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")

    with patch(
        "app.modules.imports.service.parse_csv",
        new=AsyncMock(return_value=make_parsed_csv()),
    ):
        result = asyncio.run(
            service.import_csv(uuid4(), MagicMock(), ImportMode.REPLACE)
        )

    assert events == ["delete", "insert", "commit"]
    assert result.feature_engineering_rows is None


def test_incremental_endpoint_schedules_mock_with_csv_rows() -> None:
    rows = [{"fecha": None, "item": "A"}]
    result = ImportResult(
        job=make_job(),
        mode=ImportMode.INCREMENTAL,
        feature_engineering_rows=rows,
    )
    background_tasks = BackgroundTasks()
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=background_tasks,
                file=upload,
                mode=ImportMode.INCREMENTAL,
            )
        )

    assert response.feature_engineering_status == "scheduled"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args == (rows,)
    upload.close.assert_awaited_once()


def test_replace_endpoint_does_not_schedule_feature_engineering() -> None:
    result = ImportResult(
        job=make_job(),
        mode=ImportMode.REPLACE,
        feature_engineering_rows=None,
    )
    background_tasks = BackgroundTasks()
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=background_tasks,
                file=upload,
                mode=ImportMode.REPLACE,
            )
        )

    assert response.feature_engineering_status == "not_required"
    assert background_tasks.tasks == []
