from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ImportMode(str, Enum):
    INCREMENTAL = "incremental"
    REPLACE = "replace"


class ImportResponse(BaseModel):
    id: UUID
    filename: str
    destination: str
    status: str
    total_rows: int
    inserted_rows: int
    rejected_rows: int
    columns: list[str]
    validation_errors: list[dict]
    mode: ImportMode
    feature_engineering_status: str


class ReplaceImportResponse(BaseModel):
    id: UUID
    filename: str
    destination: str
    operation: str
    status: str
    total_rows: int
    inserted_rows: int
    rejected_rows: int
    columns: list[str]
    validation_errors: list[dict]
