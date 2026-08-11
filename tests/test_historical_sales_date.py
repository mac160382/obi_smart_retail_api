import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.imports.csv_parser import CSVValidationError, parse_csv

HEADER = (
    "fecha,item,descripcion_item,location,descripcion_tienda,"
    "tipo_centro,qty_vendida\n"
)
EXPECTED_DATE = date(2026, 8, 10)


def make_upload(rows: str) -> MagicMock:
    upload = MagicMock()
    upload.filename = "ventas.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[(HEADER + rows).encode("utf-8"), b""])
    return upload


def test_historical_sales_accepts_rows_matching_form_date() -> None:
    upload = make_upload(
        "2026-08-10,ITEM-1,Producto,13,Tienda,Supermercado,12.50\n"
    )

    parsed = asyncio.run(parse_csv(upload, EXPECTED_DATE))

    assert len(parsed.rows) == 1
    assert parsed.rows[0]["fecha"] == EXPECTED_DATE


def test_historical_sales_does_not_compare_dates_without_expected_date() -> None:
    upload = make_upload(
        "2026-08-09,ITEM-1,Producto,13,Tienda,Supermercado,12.50\n"
    )

    parsed = asyncio.run(parse_csv(upload))

    assert len(parsed.rows) == 1
    assert parsed.rows[0]["fecha"] == date(2026, 8, 9)


@pytest.mark.parametrize(
    "csv_date",
    ["2026-08-09", "", "fecha-invalida"],
)
def test_historical_sales_rejects_file_when_date_does_not_match(
    csv_date: str,
) -> None:
    upload = make_upload(
        f"{csv_date},ITEM-1,Producto,13,Tienda,Supermercado,12.50\n"
    )

    with pytest.raises(
        CSVValidationError,
        match=r"fecha=2026-08-10.*Filas inválidas: 2",
    ):
        asyncio.run(parse_csv(upload, EXPECTED_DATE))
