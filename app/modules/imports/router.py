import asyncio
import logging
from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.core.config import settings
from app.dependencies.auth import CurrentUserId
from app.dependencies.database import DatabaseSession
from app.infrastructure.messaging import EventMessage
from app.modules.imports.csv_parser import CSVValidationError
from app.modules.imports.feature_engineering import run_feature_engineering
from app.modules.imports.schemas import (
    ImportMode,
    ImportResponse,
    ReplaceImportResponse,
)
from app.modules.imports.service import ImportService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/historical-sales/csv",
    response_model=ImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_historical_sales_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    background_tasks: BackgroundTasks,
    request: Request,
    file: Annotated[
        UploadFile,
        File(description="CSV de ventas históricas de productos lácteos"),
    ],
    mode: Annotated[
        ImportMode,
        Form(description="Modo de carga: incremental o reemplazo completo"),
    ],
    fecha: Annotated[
        date | None,
        Form(
            description=(
                "Fecha que debe coincidir con la columna fecha del CSV cuando "
                "publish_message es true"
            )
        ),
    ] = None,
    publish_message: Annotated[
        bool,
        Form(description="Indica si la carga solicitará publicar un mensaje"),
    ] = False,
) -> ImportResponse:
    try:
        result = await ImportService(db).import_csv(
            user_id,
            file,
            mode,
            fecha,
            publish_message,
        )
        job = result.job

        if result.feature_engineering_rows is not None:
            background_tasks.add_task(
                run_feature_engineering,
                result.feature_engineering_rows,
            )

        message_publication_status = "not_requested"
        message_event_id = None
        if result.publish_message:
            message_event_id = job.id
            try:
                if result.event_date is None:
                    raise RuntimeError("Missing event date after validation")
                event = EventMessage(
                    event_id=job.id,
                    event_type=(
                        settings.rabbitmq_historical_sales_routing_key
                    ),
                    correlation_id=str(job.id),
                    data={
                        "fecha": result.event_date.isoformat(),
                        "mode": result.mode.value,
                        "filename": job.original_filename,
                        "inserted_rows": job.inserted_rows,
                        "rejected_rows": job.rejected_rows,
                        "destination": (
                            f"{job.destination_schema}."
                            f"{job.destination_table}"
                        ),
                    },
                )
                publisher = request.app.state.rabbitmq_publisher
                await asyncio.wait_for(
                    publisher.publish(
                        event,
                        routing_key=(
                            settings.rabbitmq_historical_sales_routing_key
                        ),
                    ),
                    timeout=settings.rabbitmq_publish_timeout_seconds,
                )
                message_publication_status = "published"
            except Exception:
                message_publication_status = "failed"
                logger.exception(
                    "Historical sales import committed but RabbitMQ "
                    "publication failed",
                    extra={"import_job_id": str(job.id)},
                )

        metadata = job.columns or {}
        return ImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=(
                f"{job.destination_schema}.{job.destination_table}"
            ),
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
            mode=result.mode,
            feature_engineering_status=(
                "scheduled"
                if result.feature_engineering_rows is not None
                else "not_required"
            ),
            publish_message=result.publish_message,
            message_publication_status=message_publication_status,
            message_event_id=message_event_id,
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.post(
    "/current-promotions/csv",
    response_model=ReplaceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_current_promotions_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    file: Annotated[
        UploadFile,
        File(description="CSV de promociones vigentes de productos lácteos"),
    ],
) -> ReplaceImportResponse:
    try:
        job = await ImportService(db).import_current_promotions(user_id, file)
        metadata = job.columns or {}
        return ReplaceImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=f"{job.destination_schema}.{job.destination_table}",
            operation="replace",
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.post(
    "/inventory-master/csv",
    response_model=ReplaceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_inventory_master_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    file: Annotated[
        UploadFile,
        File(description="CSV del maestro de inventario de productos lácteos"),
    ],
) -> ReplaceImportResponse:
    try:
        job = await ImportService(db).import_inventory_master(user_id, file)
        metadata = job.columns or {}
        return ReplaceImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=f"{job.destination_schema}.{job.destination_table}",
            operation="replace",
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.post(
    "/items-master/csv",
    response_model=ReplaceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_items_master_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    file: Annotated[
        UploadFile,
        File(description="CSV del maestro de artículos lácteos"),
    ],
) -> ReplaceImportResponse:
    try:
        job = await ImportService(db).import_items_master(user_id, file)
        metadata = job.columns or {}
        return ReplaceImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=f"{job.destination_schema}.{job.destination_table}",
            operation="replace",
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.post(
    "/stores-master/csv",
    response_model=ReplaceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_stores_master_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    file: Annotated[
        UploadFile,
        File(description="CSV del maestro de tiendas de productos lácteos"),
    ],
) -> ReplaceImportResponse:
    try:
        job = await ImportService(db).import_stores_master(user_id, file)
        metadata = job.columns or {}
        return ReplaceImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=f"{job.destination_schema}.{job.destination_table}",
            operation="replace",
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.post(
    "/forecast/csv",
    response_model=ReplaceImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_forecast_csv(
    user_id: CurrentUserId,
    db: DatabaseSession,
    file: Annotated[
        UploadFile,
        File(description="CSV de pronósticos de ventas"),
    ],
) -> ReplaceImportResponse:
    try:
        job = await ImportService(db).import_forecast(user_id, file)
        metadata = job.columns or {}
        return ReplaceImportResponse(
            id=job.id,
            filename=job.original_filename,
            destination=f"{job.destination_schema}.{job.destination_table}",
            operation="replace",
            status=job.status.value,
            total_rows=job.total_rows,
            inserted_rows=job.inserted_rows,
            rejected_rows=job.rejected_rows,
            columns=metadata.get("names", []),
            validation_errors=metadata.get("validation_errors", []),
        )

    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()
