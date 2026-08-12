from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.infrastructure.messaging import (
    create_forecast_loaded_consumer,
    create_rabbitmq_publisher,
)
from app.modules.suggested_orders.events import create_sse_broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    sse_broker = create_sse_broker()
    publisher = create_rabbitmq_publisher()
    forecast_consumer = create_forecast_loaded_consumer(sse_broker)
    await publisher.connect()
    await forecast_consumer.connect()
    app.state.rabbitmq_publisher = publisher
    app.state.rabbitmq_forecast_consumer = forecast_consumer
    app.state.sse_broker = sse_broker
    try:
        yield
    finally:
        await forecast_consumer.close()
        await publisher.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Last-Event-ID",
            "Cache-Control",
        ],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(app)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
