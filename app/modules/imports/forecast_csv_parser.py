import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
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

EXPECTED_FORECAST_COLUMNS = {
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
}


@dataclass(frozen=True)
class ParsedForecastCSV:
    filename: str
    columns: list[str]
    rows: list[dict]


def optional_decimal(
    value: str,
    column: str,
    precision: int,
    scale: int,
) -> Decimal | None:
    """Validate fixed-precision values used by other import parsers."""
    normalized = value.strip()
    if not normalized:
        return None

    try:
        decimal_value = Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise CSVValidationError(
            f"{column} contiene un decimal inválido: {value}"
        ) from exc

    if not decimal_value.is_finite():
        raise CSVValidationError(
            f"{column} contiene un decimal inválido: {value}"
        )

    normalized_value = decimal_value.normalize()
    decimal_places = max(-normalized_value.as_tuple().exponent, 0)
    if decimal_places > scale:
        raise CSVValidationError(
            f"{column} admite máximo {scale} decimales: {value}"
        )

    max_absolute = Decimal(10) ** (precision - scale)
    if abs(decimal_value) >= max_absolute:
        raise CSVValidationError(
            f"{column} excede NUMERIC({precision},{scale}): {value}"
        )

    return decimal_value


def optional_float(value: str, column: str) -> float | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        decimal_value = Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise CSVValidationError(
            f"{column} contiene un número inválido: {value}"
        ) from exc

    if not decimal_value.is_finite():
        raise CSVValidationError(
            f"{column} contiene un número inválido: {value}"
        )

    return float(decimal_value)


def optional_boolean(value: str) -> bool | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise CSVValidationError(
        f"Booleano inválido: {value}. Use True, False, 1 o 0"
    )


def optional_utc_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CSVValidationError(
            f"Fecha-hora UTC inválida: {value}. Use formato ISO 8601"
        ) from exc

    if parsed.tzinfo is None:
        raise CSVValidationError(
            f"Fecha-hora UTC sin zona horaria: {value}"
        )

    return parsed.astimezone(timezone.utc)


def nonnegative_integer(value: str, column: str) -> int | None:
    integer_value = optional_integer(value)
    if integer_value is not None and integer_value < 0:
        raise CSVValidationError(
            f"{column} no puede ser negativo: {value}"
        )
    return integer_value


async def parse_forecast_csv(upload: UploadFile) -> ParsedForecastCSV:
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
    missing = EXPECTED_FORECAST_COLUMNS - column_set
    unexpected = column_set - EXPECTED_FORECAST_COLUMNS

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
                    "forecast_origin": optional_date(row["forecast_origin"]),
                    "target_date": optional_date(row["target_date"]),
                    "horizon_day": nonnegative_integer(
                        row["horizon_day"], "horizon_day"
                    ),
                    "descripcion_item": optional_text(
                        row["descripcion_item"]
                    ),
                    "item": optional_text(row["item"], 50),
                    "item_code": optional_integer(row["item_code"]),
                    "descripcion_tienda": optional_text(
                        row["descripcion_tienda"], 150
                    ),
                    "location": optional_integer(row["location"]),
                    "location_code": optional_integer(row["location_code"]),
                    "forecast_qty_vendida": optional_float(
                        row["forecast_qty_vendida"],
                        "forecast_qty_vendida",
                    ),
                    "raw_prediction": optional_float(
                        row["raw_prediction"], "raw_prediction"
                    ),
                    "was_clipped_to_zero": optional_boolean(
                        row["was_clipped_to_zero"]
                    ),
                    "unknown_item": optional_boolean(row["unknown_item"]),
                    "unknown_location": optional_boolean(
                        row["unknown_location"]
                    ),
                    "history_days": nonnegative_integer(
                        row["history_days"], "history_days"
                    ),
                    "model_key": optional_text(row["model_key"], 100),
                    "model_name": optional_text(row["model_name"], 150),
                    "model_cutoff": optional_date(row["model_cutoff"]),
                    "generated_utc": optional_utc_datetime(
                        row["generated_utc"]
                    ),
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

    return ParsedForecastCSV(
        filename=filename,
        columns=columns,
        rows=rows,
    )
