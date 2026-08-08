import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocurrió un error interno"},
        )
