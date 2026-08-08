import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.promotions_csv_parser import (
    ParsedPromotionsCSV,
    parse_promotions_csv,
)
from app.modules.imports.service import ImportService

HEADER = (
    "item,item_desc,event_code,event_name,promo_mechanic,status,inicio,fin,"
    "desc_pct,price_reg,price_promo,uplift_esperado,dias_restantes\n"
)


def make_upload(content: str) -> MagicMock:
    upload = MagicMock()
    upload.filename = "promociones.csv"
    upload.content_type = "text/csv"
    upload.read = AsyncMock(side_effect=[content.encode("utf-8"), b""])
    return upload


def valid_row() -> str:
    return "A1,Producto,E1,Evento,Descuento,ACTIVE,2026-07-01,2026-07-31,10.5,100,90,1.2500,20\n"


def test_promotions_parser_rejects_entire_file_if_one_row_is_invalid() -> None:
    invalid_row = (
        f"{'A' * 51},Producto,E1,Evento,Descuento,ACTIVE,2026-07-01,"
        "2026-07-31,10.5,100,90,1.2500,20\n"
    )

    try:
        asyncio.run(parse_promotions_csv(make_upload(HEADER + valid_row() + invalid_row)))
    except CSVValidationError as exc:
        assert "1 fila(s) inválida(s)" in str(exc)
    else:
        raise AssertionError("El parser aceptó un archivo con una fila inválida")


def test_promotions_service_replaces_then_commits() -> None:
    events: list[str] = []
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.add_job.side_effect = lambda _job: events.append("job")
    service.repository.replace_current_promotions.side_effect = (
        lambda *_args, **_kwargs: events.append("replace") or 1
    )
    db.commit.side_effect = lambda: events.append("commit")
    parsed = ParsedPromotionsCSV(
        filename="promociones.csv",
        columns=["item"],
        rows=[{"item": "A1"}],
    )

    with patch(
        "app.modules.imports.service.parse_promotions_csv",
        new=AsyncMock(return_value=parsed),
    ):
        job = asyncio.run(
            service.import_current_promotions(uuid4(), MagicMock())
        )

    assert events == ["job", "replace", "commit"]
    assert job.inserted_rows == 1
    db.rollback.assert_not_called()


def test_promotions_service_rolls_back_if_replace_fails() -> None:
    db = MagicMock()
    service = ImportService(db)
    service.repository = MagicMock()
    service.repository.replace_current_promotions.side_effect = RuntimeError(
        "database error"
    )
    parsed = ParsedPromotionsCSV(
        filename="promociones.csv",
        columns=["item"],
        rows=[{"item": "A1"}],
    )

    with patch(
        "app.modules.imports.service.parse_promotions_csv",
        new=AsyncMock(return_value=parsed),
    ):
        try:
            asyncio.run(
                service.import_current_promotions(uuid4(), MagicMock())
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("El servicio ocultó el error del repositorio")

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
