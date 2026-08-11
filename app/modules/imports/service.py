from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.imports.csv_parser import CSVValidationError, parse_csv
from app.modules.imports.forecast_csv_parser import parse_forecast_csv
from app.modules.imports.inventory_csv_parser import parse_inventory_master_csv
from app.modules.imports.items_csv_parser import parse_items_master_csv
from app.modules.imports.models import ImportJob, ImportStatus
from app.modules.imports.promotions_csv_parser import parse_promotions_csv
from app.modules.imports.repository import ImportRepository
from app.modules.imports.schemas import ImportMode
from app.modules.imports.stores_csv_parser import parse_stores_master_csv


@dataclass(frozen=True)
class ImportResult:
    job: ImportJob
    mode: ImportMode
    feature_engineering_rows: list[dict] | None
    publish_message: bool = False
    event_date: date | None = None


class ImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ImportRepository(db)

    async def import_csv(
        self,
        user_id: UUID,
        upload: UploadFile,
        mode: ImportMode,
        expected_date: date | None,
        publish_message: bool = False,
    ) -> ImportResult:
        if publish_message and expected_date is None:
            raise CSVValidationError(
                "El parámetro fecha es obligatorio cuando "
                "publish_message=true"
            )

        parsed = await parse_csv(
            upload,
            expected_date if publish_message else None,
        )

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.database_schema,
            destination_table=settings.historical_sales_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows) + parsed.rejected_rows,
            inserted_rows=0,
            rejected_rows=parsed.rejected_rows,
            columns={
                "names": parsed.columns,
                "validation_errors": parsed.errors,
            },
        )

        try:
            self.repository.add_job(job)

            if mode is ImportMode.REPLACE:
                self.repository.delete_historical_sales()

            inserted = self.repository.bulk_insert_historical_sales(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )

            job.inserted_rows = inserted
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return ImportResult(
                job=job,
                mode=mode,
                feature_engineering_rows=(
                    parsed.rows
                    if mode is ImportMode.INCREMENTAL
                    else None
                ),
                publish_message=publish_message,
                event_date=expected_date if publish_message else None,
            )

        except Exception as exc:
            self.db.rollback()
            raise exc

    async def import_current_promotions(
        self,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJob:
        parsed = await parse_promotions_csv(upload)

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.current_promotions_schema,
            destination_table=settings.current_promotions_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows),
            inserted_rows=0,
            rejected_rows=0,
            columns={"names": parsed.columns, "validation_errors": []},
        )

        try:
            self.repository.add_job(job)
            job.inserted_rows = self.repository.replace_current_promotions(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception:
            self.db.rollback()
            raise

    async def import_inventory_master(
        self,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJob:
        parsed = await parse_inventory_master_csv(upload)

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.inventory_master_schema,
            destination_table=settings.inventory_master_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows),
            inserted_rows=0,
            rejected_rows=0,
            columns={"names": parsed.columns, "validation_errors": []},
        )

        try:
            self.repository.add_job(job)
            job.inserted_rows = self.repository.replace_inventory_master(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception:
            self.db.rollback()
            raise

    async def import_items_master(
        self,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJob:
        parsed = await parse_items_master_csv(upload)

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.items_master_schema,
            destination_table=settings.items_master_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows),
            inserted_rows=0,
            rejected_rows=0,
            columns={"names": parsed.columns, "validation_errors": []},
        )

        try:
            self.repository.add_job(job)
            job.inserted_rows = self.repository.replace_items_master(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception:
            self.db.rollback()
            raise

    async def import_stores_master(
        self,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJob:
        parsed = await parse_stores_master_csv(upload)

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.stores_master_schema,
            destination_table=settings.stores_master_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows),
            inserted_rows=0,
            rejected_rows=0,
            columns={"names": parsed.columns, "validation_errors": []},
        )

        try:
            self.repository.add_job(job)
            job.inserted_rows = self.repository.replace_stores_master(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception:
            self.db.rollback()
            raise

    async def import_forecast(
        self,
        user_id: UUID,
        upload: UploadFile,
    ) -> ImportJob:
        parsed = await parse_forecast_csv(upload)

        job = ImportJob(
            user_id=user_id,
            original_filename=parsed.filename,
            destination_schema=settings.forecast_schema,
            destination_table=settings.forecast_table,
            status=ImportStatus.PROCESSING,
            total_rows=len(parsed.rows),
            inserted_rows=0,
            rejected_rows=0,
            columns={"names": parsed.columns, "validation_errors": []},
        )

        try:
            self.repository.add_job(job)
            job.inserted_rows = self.repository.replace_forecast(
                parsed.rows,
                batch_size=settings.csv_batch_size,
            )
            job.status = ImportStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(job)
            return job

        except Exception:
            self.db.rollback()
            raise
