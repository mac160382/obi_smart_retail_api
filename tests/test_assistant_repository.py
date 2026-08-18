from datetime import date
from unittest.mock import MagicMock

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
