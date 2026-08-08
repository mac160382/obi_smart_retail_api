from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUserId
from app.dependencies.database import DatabaseSession
from app.modules.catalogs.schemas import LocationCatalogItem
from app.modules.catalogs.service import CatalogService

router = APIRouter()


@router.get(
    "/locations",
    response_model=list[LocationCatalogItem],
    status_code=status.HTTP_200_OK,
)
def get_locations_catalog(
    _user_id: CurrentUserId,
    db: DatabaseSession,
) -> list[LocationCatalogItem]:
    locations = CatalogService(db).get_locations()
    return [LocationCatalogItem.model_validate(item) for item in locations]
