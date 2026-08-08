from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.imports.models import g2_maestro_inventario_lacteos


def build_locations_catalog_query() -> Select[tuple[str, str]]:
    inventory = g2_maestro_inventario_lacteos
    location = func.trim(inventory.c.location_code).label("location")
    store_description = func.trim(
        func.coalesce(inventory.c.description_location_code, "")
    ).label("descripcion_tienda")

    return (
        select(location, store_description)
        .where(
            inventory.c.location_code.is_not(None),
            func.trim(inventory.c.location_code) != "",
        )
        .distinct()
        .order_by(store_description, location)
    )


class CatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_locations(self) -> list[dict[str, str]]:
        rows = self.db.execute(build_locations_catalog_query()).mappings().all()
        return [
            {
                "location": str(row["location"]),
                "descripcion_tienda": str(row["descripcion_tienda"]),
            }
            for row in rows
        ]
