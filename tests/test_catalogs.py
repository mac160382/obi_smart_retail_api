from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.main import app
from app.modules.catalogs.repository import (
    CatalogRepository,
    build_locations_catalog_query,
)


def test_locations_query_returns_unique_non_empty_locations() -> None:
    sql = str(
        build_locations_catalog_query().compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "SELECT DISTINCT" in sql
    assert "trim(public.g2_maestro_inventario_lacteos.location_code) AS location" in sql
    assert "description_location_code" in sql
    assert "location_code IS NOT NULL" in sql
    assert "trim(public.g2_maestro_inventario_lacteos.location_code) != ''" in sql
    assert "ORDER BY descripcion_tienda, location" in sql


def test_repository_maps_location_catalog_rows() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"location": "13", "descripcion_tienda": "Tienda Centro"},
        {"location": "21", "descripcion_tienda": "Tienda Norte"},
    ]

    result = CatalogRepository(db).get_locations()

    assert result == [
        {"location": "13", "descripcion_tienda": "Tienda Centro"},
        {"location": "21", "descripcion_tienda": "Tienda Norte"},
    ]
    db.execute.assert_called_once()


def test_locations_catalog_route_is_registered() -> None:
    operation = app.openapi()["paths"]["/api/v1/catalogs/locations"]

    assert "get" in operation
