from sqlalchemy.orm import Session

from app.modules.catalogs.repository import CatalogRepository


class CatalogService:
    def __init__(self, db: Session) -> None:
        self.repository = CatalogRepository(db)

    def get_locations(self) -> list[dict[str, str]]:
        return self.repository.get_locations()
