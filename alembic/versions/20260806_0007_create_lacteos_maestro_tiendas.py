"""Create public.lacteos_maestro_tiendas.

Revision ID: 20260806_0007
Revises: 20260806_0006
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260806_0007"
down_revision: Union[str, None] = "20260806_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "lacteos_maestro_tiendas"
OWNER = "smartadmin"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("location", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.String(150), nullable=True),
        sa.Column("tipo_centro", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("estado", sa.Integer(), nullable=True),
        sa.Column("sociedad", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(f'ALTER TABLE "{SCHEMA}"."{TABLE}" OWNER TO "{OWNER}"')
    )


def downgrade() -> None:
    op.drop_table(TABLE, schema=SCHEMA)
