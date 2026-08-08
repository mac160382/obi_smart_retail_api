from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.catalogs.router import router as catalogs_router
from app.modules.imports.router import router as imports_router
from app.modules.suggested_orders.router import router as suggested_orders_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(catalogs_router, prefix="/catalogs", tags=["catalogs"])
api_router.include_router(imports_router, prefix="/imports", tags=["imports"])
api_router.include_router(
    suggested_orders_router,
    prefix="/suggested-orders",
    tags=["suggested-orders"],
)
