import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks

from app.modules.imports.csv_parser import CSVValidationError, ParsedCSV
from app.modules.imports.models import ImportStatus
from app.modules.imports.router import upload_historical_sales_csv
from app.modules.imports.schemas import ImportMode
from app.modules.imports.service import ImportResult, ImportService

EXPECTED_DATE = date(2026, 8, 10)


def make_parsed_csv() -> ParsedCSV:
    return ParsedCSV(
        filename="ventas.csv",
        columns=["fecha", "item"],
        rows=[{"fecha": EXPECTED_DATE, "item": "A"}],
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
            service.import_csv(
                uuid4(),
                MagicMock(),
                ImportMode.INCREMENTAL,
                EXPECTED_DATE,
            )
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
            service.import_csv(
                uuid4(),
                MagicMock(),
                ImportMode.REPLACE,
                EXPECTED_DATE,
            )
        )

    assert events == ["delete", "insert", "commit"]
    assert result.feature_engineering_rows is None


def test_publish_message_requires_date_before_parsing_or_writing() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()

    with patch(
        "app.modules.imports.service.parse_csv",
        new=AsyncMock(),
    ) as parser:
        with pytest.raises(
            CSVValidationError,
            match="fecha es obligatorio.*publish_message=true",
        ):
            asyncio.run(
                service.import_csv(
                    uuid4(),
                    MagicMock(),
                    ImportMode.INCREMENTAL,
                    None,
                    True,
                )
            )

    parser.assert_not_awaited()
    service.repository.add_job.assert_not_called()
    service.repository.bulk_insert_historical_sales.assert_not_called()
    db.commit.assert_not_called()


def test_publish_message_applies_date_validation_and_preserves_event_data() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.bulk_insert_historical_sales.return_value = 1
    upload = MagicMock()
    parser = AsyncMock(return_value=make_parsed_csv())

    with patch("app.modules.imports.service.parse_csv", new=parser):
        result = asyncio.run(
            service.import_csv(
                uuid4(),
                upload,
                ImportMode.INCREMENTAL,
                EXPECTED_DATE,
                True,
            )
        )

    parser.assert_awaited_once_with(upload, EXPECTED_DATE)
    assert result.publish_message is True
    assert result.event_date == EXPECTED_DATE


def test_incremental_endpoint_schedules_mock_with_csv_rows() -> None:
    rows = [{"fecha": EXPECTED_DATE, "item": "A"}]
    result = ImportResult(
        job=make_job(),
        mode=ImportMode.INCREMENTAL,
        feature_engineering_rows=rows,
    )
    background_tasks = BackgroundTasks()
    request = MagicMock()
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=background_tasks,
                request=request,
                file=upload,
                mode=ImportMode.INCREMENTAL,
                fecha=EXPECTED_DATE,
                publish_message=False,
            )
        )

    assert response.feature_engineering_status == "scheduled"
    assert response.publish_message is False
    assert response.message_publication_status == "not_requested"
    assert response.message_event_id is None
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
    request = MagicMock()
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=background_tasks,
                request=request,
                file=upload,
                mode=ImportMode.REPLACE,
                fecha=EXPECTED_DATE,
                publish_message=False,
            )
        )

    assert response.feature_engineering_status == "not_required"
    assert response.message_publication_status == "not_requested"
    assert background_tasks.tasks == []


def test_endpoint_publishes_confirmed_event_after_successful_import() -> None:
    result = ImportResult(
        job=make_job(),
        mode=ImportMode.INCREMENTAL,
        feature_engineering_rows=None,
        publish_message=True,
        event_date=EXPECTED_DATE,
    )
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    request = MagicMock()
    request.app.state.rabbitmq_publisher = publisher
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=BackgroundTasks(),
                request=request,
                file=upload,
                mode=ImportMode.INCREMENTAL,
                fecha=EXPECTED_DATE,
                publish_message=True,
            )
        )

    event = publisher.publish.await_args.args[0]
    assert event.event_type == "historical_sales.imported"
    assert event.data["fecha"] == "2026-08-10"
    assert event.event_id == result.job.id
    assert publisher.publish.await_args.kwargs == {
        "routing_key": "historical_sales.imported"
    }
    assert response.message_publication_status == "published"
    assert response.message_event_id == result.job.id


def test_endpoint_reports_failed_publication_without_undoing_import() -> None:
    result = ImportResult(
        job=make_job(),
        mode=ImportMode.REPLACE,
        feature_engineering_rows=None,
        publish_message=True,
        event_date=EXPECTED_DATE,
    )
    publisher = MagicMock()
    publisher.publish = AsyncMock(side_effect=RuntimeError("broker unavailable"))
    request = MagicMock()
    request.app.state.rabbitmq_publisher = publisher
    upload = MagicMock()
    upload.close = AsyncMock()

    with patch("app.modules.imports.router.ImportService") as service_class:
        service_class.return_value.import_csv = AsyncMock(return_value=result)
        response = asyncio.run(
            upload_historical_sales_csv(
                user_id=uuid4(),
                db=MagicMock(),
                background_tasks=BackgroundTasks(),
                request=request,
                file=upload,
                mode=ImportMode.REPLACE,
                fecha=EXPECTED_DATE,
                publish_message=True,
            )
        )

    assert response.status == "completed"
    assert response.message_publication_status == "failed"
    assert response.message_event_id == result.job.id
