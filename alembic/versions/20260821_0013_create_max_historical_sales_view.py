"""Create maximum historical sales view.

Revision ID: 20260821_0013
Revises: 20260819_0012
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0013"
down_revision: str | None = "20260819_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
SOURCE_TABLE = "lacteos_ventas_historicas"
VIEW_NAME = "vst_max_vta_historica"
OWNER = "smartadmin"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE VIEW "{SCHEMA}"."{VIEW_NAME}" AS
            SELECT
                item,
                location,
                MAX(qty_vendida) AS max_qty_vendida
            FROM "{SCHEMA}"."{SOURCE_TABLE}"
            GROUP BY item, location
            """
        )
    )
    op.execute(
        sa.text(
            f'ALTER VIEW "{SCHEMA}"."{VIEW_NAME}" OWNER TO "{OWNER}"'
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(f'DROP VIEW IF EXISTS "{SCHEMA}"."{VIEW_NAME}"')
    )
