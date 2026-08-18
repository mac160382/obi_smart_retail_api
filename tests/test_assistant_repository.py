from datetime import date
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
