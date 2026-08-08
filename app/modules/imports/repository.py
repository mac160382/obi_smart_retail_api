from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Table, delete, insert
from sqlalchemy.orm import Session

from app.modules.imports.models import (
    ImportJob,
    g2_lacteos_promociones_vigentes,
    g2_maestro_inventario_lacteos,
    lacteos_maestro_items,
    lacteos_maestro_tiendas,
    lacteos_ventas_historicas,
    pronostico,
)


class ImportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_job(self, job: ImportJob) -> ImportJob:
        self.db.add(job)
        self.db.flush()
        return job

    def bulk_insert_historical_sales(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        inserted = 0
        batch: list[dict] = []

        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                self.db.execute(
                    insert(lacteos_ventas_historicas),
                    batch,
                )
                inserted += len(batch)
                batch.clear()

        if batch:
            self.db.execute(
                insert(lacteos_ventas_historicas),
                batch,
            )
            inserted += len(batch)

        return inserted

    def delete_historical_sales(self) -> None:
        self.db.execute(delete(lacteos_ventas_historicas))

    def replace_current_promotions(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        return self._replace_rows(
            g2_lacteos_promociones_vigentes,
            rows,
            batch_size,
        )

    def replace_inventory_master(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        return self._replace_rows(
            g2_maestro_inventario_lacteos,
            rows,
            batch_size,
        )

    def replace_items_master(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        return self._replace_rows(
            lacteos_maestro_items,
            rows,
            batch_size,
        )

    def replace_stores_master(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        return self._replace_rows(
            lacteos_maestro_tiendas,
            rows,
            batch_size,
        )

    def replace_forecast(
        self,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        return self._replace_rows(
            pronostico,
            rows,
            batch_size,
        )

    def _replace_rows(
        self,
        table: Table,
        rows: Iterable[dict],
        batch_size: int,
    ) -> int:
        self.db.execute(delete(table))

        inserted = 0
        batch: list[dict] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                self.db.execute(
                    insert(table),
                    batch,
                )
                inserted += len(batch)
                batch.clear()

        if batch:
            self.db.execute(
                insert(table),
                batch,
            )
            inserted += len(batch)

        return inserted

    def get_job(self, job_id: UUID) -> ImportJob | None:
        return self.db.get(ImportJob, job_id)
