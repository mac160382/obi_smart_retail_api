"""Replace pronostico with the generated forecast schema.

Revision ID: 20260807_0008
Revises: 20260806_0007
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0008"
down_revision: Union[str, None] = "20260806_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pronostico"
OWNER = "smartadmin"


def set_table_owner() -> None:
    op.execute(
        sa.text(f'ALTER TABLE "{SCHEMA}"."{TABLE}" OWNER TO "{OWNER}"')
    )


def upgrade() -> None:
    op.drop_table(TABLE, schema=SCHEMA)
    op.create_table(
        TABLE,
        sa.Column("forecast_origin", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("horizon_day", sa.Integer(), nullable=True),
        sa.Column("descripcion_item", sa.Text(), nullable=True),
        sa.Column("item", sa.String(50), nullable=True),
        sa.Column("item_code", sa.Integer(), nullable=True),
        sa.Column("descripcion_tienda", sa.String(150), nullable=True),
        sa.Column("location", sa.Integer(), nullable=True),
        sa.Column("location_code", sa.Integer(), nullable=True),
        sa.Column(
            "forecast_qty_vendida",
            postgresql.DOUBLE_PRECISION(),
            nullable=True,
        ),
        sa.Column(
            "raw_prediction",
            postgresql.DOUBLE_PRECISION(),
            nullable=True,
        ),
        sa.Column("was_clipped_to_zero", sa.Boolean(), nullable=True),
        sa.Column("unknown_item", sa.Boolean(), nullable=True),
        sa.Column("unknown_location", sa.Boolean(), nullable=True),
        sa.Column("history_days", sa.Integer(), nullable=True),
        sa.Column("model_key", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(150), nullable=True),
        sa.Column("model_cutoff", sa.Date(), nullable=True),
        sa.Column(
            "generated_utc",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    set_table_owner()


def downgrade() -> None:
    op.drop_table(TABLE, schema=SCHEMA)
    op.create_table(
        TABLE,
        sa.Column("item", sa.String(50), nullable=True),
        sa.Column("precio_unit_usd", sa.Numeric(18, 4), nullable=True),
        sa.Column("location", sa.Integer(), nullable=True),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=True),
        sa.Column("month", sa.SmallInteger(), nullable=True),
        sa.Column("day_of_month", sa.SmallInteger(), nullable=True),
        sa.Column("is_weekend", sa.Boolean(), nullable=True),
        sa.Column("lag_1", sa.Numeric(18, 4), nullable=True),
        sa.Column("lag_7", sa.Numeric(18, 4), nullable=True),
        sa.Column("lag_14", sa.Numeric(18, 4), nullable=True),
        sa.Column("lag_28", sa.Numeric(18, 4), nullable=True),
        sa.Column("rolling_mean_7", sa.Numeric(20, 9), nullable=True),
        sa.Column("rolling_mean_14", sa.Numeric(20, 9), nullable=True),
        sa.Column("rolling_mean_28", sa.Numeric(20, 9), nullable=True),
        sa.Column("trend_index", sa.Integer(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("quarter", sa.SmallInteger(), nullable=True),
        sa.Column("qty_vendida", sa.Numeric(18, 4), nullable=True),
        sa.Column("prediccion", sa.Numeric(20, 9), nullable=True),
        schema=SCHEMA,
    )
    set_table_owner()
