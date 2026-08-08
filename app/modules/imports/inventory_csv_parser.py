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
    optional_date,
    optional_integer,
    optional_text,
    read_limited,
)
from app.modules.imports.promotions_csv_parser import optional_numeric_18_4

TEXT_COLUMNS = {
    "item_code": 50,
    "description_item_code": 60,
    "proveedor_code": 50,
    "description_proveedor": 67,
    "macrofamily_code": 50,
    "description_macrofamily_code": 50,
    "familia_code": 50,
    "description_familia": 50,
    "description_subagrupacion": 50,
    "location_code": 50,
    "description_location_code": 50,
    "item_type": 50,
    "estado_articulo": 50,
    "temporal_freeattr5": 50,
    "control_type": 50,
    "estado_planificacion": 50,
    "logistic_class_code": 50,
    "abc_cadena": 50,
    "frecuencia_pedido": 50,
}

NUMERIC_COLUMNS = {
    "service_level",
    "minimum_handling_quantity_units",
    "current_stock_units",
    "expected_demand_qty_period_direct_sales_units_day",
    "cobertura",
    "on_order_in_transit_units",
    "cantidad_ultimo_ingreso",
}

INTEGER_COLUMNS = {
    "lead_time_days",
    "review_period_days",
    "extra_visibilidad_units",
    "overstock_units",
}

DATE_COLUMNS = {"item_birth_day_date", "fecha_ultimo_ingreso"}
EXPECTED_INVENTORY_COLUMNS = (
    set(TEXT_COLUMNS) | NUMERIC_COLUMNS | INTEGER_COLUMNS | DATE_COLUMNS
)


@dataclass(frozen=True)
class ParsedInventoryMasterCSV:
    filename: str
    columns: list[str]
    rows: list[dict]


async def parse_inventory_master_csv(
    upload: UploadFile,
) -> ParsedInventoryMasterCSV:
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
    missing = EXPECTED_INVENTORY_COLUMNS - column_set
    unexpected = column_set - EXPECTED_INVENTORY_COLUMNS

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
                    column: optional_numeric_18_4(row[column], column)
                    for column in NUMERIC_COLUMNS
                }
            )
            parsed_row.update(
                {
                    column: optional_integer(row[column])
                    for column in INTEGER_COLUMNS
                }
            )
            parsed_row.update(
                {
                    column: optional_date(row[column])
                    for column in DATE_COLUMNS
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

    return ParsedInventoryMasterCSV(
        filename=filename,
        columns=columns,
        rows=rows,
    )
