"""Add required forecast fields to pedido_sugerido.

Revision ID: 20260808_0009
Revises: 20260807_0008
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260808_0009"
down_revision: Union[str, None] = "20260807_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pedido_sugerido"


def upgrade() -> None:
    # Los registros existentes no tienen un origen de pronóstico confiable.
    op.execute(sa.text(f'DELETE FROM "{SCHEMA}"."{TABLE}"'))
    op.add_column(
        TABLE,
        sa.Column("forecast_origin", sa.Date(), nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column("horizon_day", sa.Integer(), nullable=False),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column("target_date", sa.Date(), nullable=False),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "target_date", schema=SCHEMA)
    op.drop_column(TABLE, "horizon_day", schema=SCHEMA)
    op.drop_column(TABLE, "forecast_origin", schema=SCHEMA)
