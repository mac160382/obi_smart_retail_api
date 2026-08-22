from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SuggestedOrderCalculationResponse(BaseModel):
    operation: Literal["replace"]
    destination: str
    status: Literal["completed"]
    deleted_rows: int
    inserted_rows: int
    calculated_at: datetime
    duration_ms: int


class SuggestedOrderItem(BaseModel):
    item: str
    forecast_origin: date
    horizon_day: int
    target_date: date
    location: int
    descripcion_tienda: str
    descripcion_item: str
    descripcion_proveedor: str
    prediccion: float
    ajustado: float | None
    observaciones: str | None
    approved_by: UUID | None
    approved_at: datetime | None
    updated_at: datetime | None
    lead_time_days: int
    review_period_days: int
    uplift_esperado: float
    minimum_handling_quantity_units: int
    current_stock_units: int
    on_order_in_transit_units: int
    sugerido: int
    max_qty_vendida: int
    safety_stock: int
    reorder_point: int
    status: Literal["Estimado", "Planificado", "Aprobado"]


class SuggestedOrderPageResponse(BaseModel):
    location: int
    forecast_origin: date | None = None
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[SuggestedOrderItem]


class SuggestedOrderBatchUpdateItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item: str = Field(min_length=1, max_length=50)
    location: int
    forecast_origin: date
    ajustado: float = Field(allow_inf_nan=False)
    observaciones: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )


class SuggestedOrderBatchUpdateRequest(BaseModel):
    items: list[SuggestedOrderBatchUpdateItem] = Field(
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "SuggestedOrderBatchUpdateRequest":
        keys = [
            (item.item, item.location, item.forecast_origin)
            for item in self.items
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "No se permite repetir item, location y forecast_origin "
                "dentro del mismo batch"
            )
        return self


class SuggestedOrderBatchUpdateResponse(BaseModel):
    batch_id: UUID
    status: Literal["completed"]
    requested_items: int
    updated_items: int
    approved_at: datetime
    items: list[SuggestedOrderItem]


class SuggestedOrderHistoryItem(BaseModel):
    change_id: UUID
    batch_id: UUID
    item: str
    location: int
    forecast_origin: date
    horizon_day: int
    target_date: date
    ajustado_anterior: float | None
    ajustado_nuevo: float
    observaciones_anteriores: str | None
    observaciones_nuevas: str | None
    status_anterior: Literal["Estimado", "Planificado", "Aprobado"]
    status_nuevo: Literal["Aprobado"]
    modified_by: UUID
    modified_at: datetime


class SuggestedOrderHistoryPageResponse(BaseModel):
    item: str
    location: int
    forecast_origin: date
    horizon_day: Literal[1]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[SuggestedOrderHistoryItem]
