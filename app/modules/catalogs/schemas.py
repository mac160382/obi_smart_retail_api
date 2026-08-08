from pydantic import BaseModel


class LocationCatalogItem(BaseModel):
    location: str
    descripcion_tienda: str
