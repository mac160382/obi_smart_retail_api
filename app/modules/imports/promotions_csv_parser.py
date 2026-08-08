import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.modules.imports.csv_parser import (
    ALLOWED_CONTENT_TYPES,
    CSVValidationError,
    normalize_column,
    optional_date,
    optional_integer,
    optional_text,
    read_limited,
)

EXPECTED_PROMOTION_COLUMNS = {
    "item",
    "item_desc",
    "event_code",
    "event_name",
    "promo_mechanic",
    "status",
    "inicio",
    "fin",
    "desc_pct",
    "price_reg",
    "price_promo",
    "uplift_esperado",
    "dias_restantes",
}


@dataclass(frozen=True)
class ParsedPromotionsCSV:
    filename: str
    columns: list[str]
    rows: list[dict]


def optional_numeric_18_4(value: str, column: str) -> Decimal | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        decimal_value = Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise CSVValidationError(
            f"{column} contiene un decimal inválido: {value}"
        ) from exc

    if decimal_value.as_tuple().exponent < -4:
        raise CSVValidationError(
            f"{column} admite máximo 4 decimales: {value}"
        )
    if abs(decimal_value) >= Decimal("100000000000000"):
        raise CSVValidationError(
            f"{column} excede NUMERIC(18,4): {value}"
        )

    return decimal_value


async def parse_promotions_csv(upload: UploadFile) -> ParsedPromotionsCSV:
    filename = Path(upload.filename or "").name

    if not filename.lower().endswith(".csv"):
        raise CSVValidationError("Solo se permiten archivos con extensión .csv")
    if upload.content_type and upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise CSVValidationError(
            f"Content-Type no permitido: {upload.content_type}"
        )

    raw = await read_limited(upload)
    if not raw:
        raise CSVValidationError("El archivo está vacío")
    if b"\x00" in raw:
        raise CSVValidationError("El archivo contiene bytes nulos")

    try:
        text = raw.decode(settings.csv_encoding)
    except UnicodeDecodeError as exc:
        raise CSVValidationError(
            f"El archivo debe usar la codificación {settings.csv_encoding}"
        ) from exc

    reader = csv.DictReader(
        io.StringIO(text, newline=""),
        delimiter=settings.csv_delimiter,
    )
    if not reader.fieldnames:
        raise CSVValidationError("No se encontró el encabezado del CSV")

    columns = [normalize_column(column) for column in reader.fieldnames]
    column_set = set(columns)
    missing = EXPECTED_PROMOTION_COLUMNS - column_set
    unexpected = column_set - EXPECTED_PROMOTION_COLUMNS

    if missing:
        raise CSVValidationError(
            "Faltan columnas: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise CSVValidationError(
            "Columnas no reconocidas: " + ", ".join(sorted(unexpected))
        )
    if len(columns) != len(column_set):
        raise CSVValidationError("El archivo contiene encabezados duplicados")

    rows: list[dict] = []
    errors: list[dict] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = {
            normalize_column(key): (value or "")
            for key, value in raw_row.items()
            if key is not None
        }

        try:
            if raw_row.get(None):
                raise CSVValidationError("La fila contiene columnas adicionales")

            rows.append(
                {
                    "item": optional_text(row["item"], 50),
                    "item_desc": optional_text(row["item_desc"], 60),
                    "event_code": optional_text(row["event_code"], 51),
                    "event_name": optional_text(row["event_name"], 68),
                    "promo_mechanic": optional_text(row["promo_mechanic"], 50),
                    "status": optional_text(row["status"], 50),
                    "inicio": optional_date(row["inicio"]),
                    "fin": optional_date(row["fin"]),
                    "desc_pct": optional_numeric_18_4(
                        row["desc_pct"], "desc_pct"
                    ),
                    "price_reg": optional_text(row["price_reg"]),
                    "price_promo": optional_text(row["price_promo"]),
                    "uplift_esperado": optional_numeric_18_4(
                        row["uplift_esperado"], "uplift_esperado"
                    ),
                    "dias_restantes": optional_integer(row["dias_restantes"]),
                }
            )
        except CSVValidationError as exc:
            errors.append({"row": row_number, "error": str(exc)})

    if errors:
        details = "; ".join(
            f"fila {error['row']}: {error['error']}"
            for error in errors[:5]
        )
        raise CSVValidationError(
            f"El archivo contiene {len(errors)} fila(s) inválida(s). {details}"
        )
    if not rows:
        raise CSVValidationError("No hay filas para insertar")

    return ParsedPromotionsCSV(
        filename=filename,
        columns=columns,
        rows=rows,
    )
