from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


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
    lead_time_days: int
    review_period_days: int
    uplift_esperado: float
    minimum_handling_quantity_units: int
    current_stock_units: int
    on_order_in_transit_units: int
    sugerido: int
    status: Literal["Estimado", "Planificado", "Aprobado"]


class SuggestedOrderPageResponse(BaseModel):
    location: int
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[SuggestedOrderItem]
