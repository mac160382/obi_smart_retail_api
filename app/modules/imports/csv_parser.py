import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

EXPECTED_COLUMNS = {
    "fecha",
    "item",
    "descripcion_item",
    "location",
    "descripcion_tienda",
    "tipo_centro",
    "qty_vendida",
}

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
}


class CSVValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCSV:
    filename: str
    columns: list[str]
    rows: list[dict]
    rejected_rows: int
    errors: list[dict]


def normalize_column(value: str) -> str:
    return value.strip().lower()


async def read_limited(upload: UploadFile) -> bytes:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    buffer = bytearray()

    while chunk := await upload.read(1024 * 1024):
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise CSVValidationError(
                f"El archivo supera el límite de {settings.max_upload_size_mb} MB"
            )

    return bytes(buffer)


def optional_text(value: str, max_length: int | None = None) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    if max_length is not None and len(normalized) > max_length:
        raise CSVValidationError(
            f"Texto con {len(normalized)} caracteres; máximo permitido: {max_length}"
        )
    return normalized


def optional_date(value: str):
    normalized = value.strip()
    if not normalized:
        return None

    accepted_formats = ("%Y-%m-%d", "%d/%m/%Y")
    for date_format in accepted_formats:
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue

    raise CSVValidationError(
        f"Fecha inválida: {normalized}. Use YYYY-MM-DD o DD/MM/YYYY"
    )


def optional_integer(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise CSVValidationError(f"Entero inválido: {normalized}") from exc


def optional_decimal(value: str) -> Decimal | None:
    normalized = value.strip()
    if not normalized:
        return None

    # Permite CSV con decimal 12.50 o 12,50 cuando el valor viene entre comillas.
    normalized = normalized.replace(",", ".")
    try:
        decimal_value = Decimal(normalized)
    except InvalidOperation as exc:
        raise CSVValidationError(f"Cantidad inválida: {value}") from exc

    if decimal_value.as_tuple().exponent < -2:
        raise CSVValidationError(
            f"qty_vendida admite máximo 2 decimales: {value}"
        )
    if abs(decimal_value) >= Decimal("1000000000000"):
        raise CSVValidationError(
            f"qty_vendida excede NUMERIC(14,2): {value}"
        )

    return decimal_value


async def parse_csv(
    upload: UploadFile,
    expected_date: date | None = None,
) -> ParsedCSV:
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

    missing = EXPECTED_COLUMNS - column_set
    unexpected = column_set - EXPECTED_COLUMNS

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
    date_errors: list[dict] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = {
            normalize_column(key): (value or "")
            for key, value in raw_row.items()
            if key is not None
        }

        try:
            row_date = optional_date(row["fecha"])
        except CSVValidationError as exc:
            error = {
                "row": row_number,
                "error": str(exc),
            }
            if expected_date is not None:
                date_errors.append(error)
            else:
                errors.append(error)
            continue

        if expected_date is not None and row_date != expected_date:
            received_date = row_date.isoformat() if row_date else "vacía"
            date_errors.append(
                {
                    "row": row_number,
                    "error": (
                        f"fecha {received_date}; se esperaba "
                        f"{expected_date.isoformat()}"
                    ),
                }
            )
            continue

        try:
            rows.append(
                {
                    "fecha": row_date,
                    "item": optional_text(row["item"], 50),
                    "descripcion_item": optional_text(row["descripcion_item"]),
                    "location": optional_integer(row["location"]),
                    "descripcion_tienda": optional_text(
                        row["descripcion_tienda"], 150
                    ),
                    "tipo_centro": optional_text(row["tipo_centro"], 100),
                    "qty_vendida": optional_decimal(row["qty_vendida"]),
                }
            )
        except CSVValidationError as exc:
            errors.append(
                {
                    "row": row_number,
                    "error": str(exc),
                }
            )

    if expected_date is not None and date_errors:
        invalid_rows = ", ".join(
            str(error["row"])
            for error in date_errors[:20]
        )
        raise CSVValidationError(
            "La columna fecha debe coincidir en todas las filas con el "
            f"parámetro fecha={expected_date.isoformat()}. "
            f"Filas inválidas: {invalid_rows}"
        )

    if not rows:
        raise CSVValidationError(
            "No hay filas válidas para insertar"
        )

    return ParsedCSV(
        filename=filename,
        columns=columns,
        rows=rows,
        rejected_rows=len(errors),
        errors=errors[:100],
    )
