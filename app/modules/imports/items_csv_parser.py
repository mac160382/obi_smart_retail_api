import csv
import io
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.modules.imports.csv_parser import (
    ALLOWED_CONTENT_TYPES,
    CSVValidationError,
    normalize_column,
    optional_integer,
    optional_text,
    read_limited,
)
from app.modules.imports.forecast_csv_parser import optional_decimal

TEXT_COLUMNS = {
    "item": 50,
    "descripcion": None,
    "desc_itemtype": 100,
    "munit": 20,
    "desc_servclas": 150,
    "division_desc": 100,
    "macrofam_desc": 100,
    "familia_desc": 150,
    "subfamilia_desc": 150,
    "des_jerar_nivel3": 150,
    "des_jerar_nivel4": 150,
    "des_jerar_nivel5": 150,
    "des_jerar_nivel6": 150,
}

INTEGER_COLUMNS = {
    "itemtype",
    "servclas",
    "division_cod",
    "macrofam_cod",
    "familia_cod",
    "subfamilia_cod",
}

NUMERIC_COLUMNS = {
    "unitcost": (14, 4),
    "listprice": (14, 4),
    "vida_util": (14, 2),
    "cod_jerarq_nivel3": (14, 0),
    "cod_jerarq_nivel4": (14, 0),
    "cod_jerarq_nivel5": (14, 0),
    "cod_jerarq_nivel6": (14, 0),
}

EXPECTED_ITEMS_COLUMNS = set(TEXT_COLUMNS) | INTEGER_COLUMNS | set(NUMERIC_COLUMNS)


@dataclass(frozen=True)
class ParsedItemsMasterCSV:
    filename: str
    columns: list[str]
    rows: list[dict]


async def parse_items_master_csv(
    upload: UploadFile,
) -> ParsedItemsMasterCSV:
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
    missing = EXPECTED_ITEMS_COLUMNS - column_set
    unexpected = column_set - EXPECTED_ITEMS_COLUMNS

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

            parsed_row = {
                column: optional_text(row[column], max_length)
                for column, max_length in TEXT_COLUMNS.items()
            }
            parsed_row.update(
                {
                    column: optional_integer(row[column])
                    for column in INTEGER_COLUMNS
                }
            )
            parsed_row.update(
                {
                    column: optional_decimal(
                        row[column], column, precision, scale
                    )
                    for column, (precision, scale) in NUMERIC_COLUMNS.items()
                }
            )
            rows.append(parsed_row)

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

    return ParsedItemsMasterCSV(
        filename=filename,
        columns=columns,
        rows=rows,
    )
