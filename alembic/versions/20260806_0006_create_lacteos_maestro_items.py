"""Create public.lacteos_maestro_items.

Revision ID: 20260806_0006
Revises: 20260719_0005
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260806_0006"
down_revision: Union[str, None] = "20260719_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "lacteos_maestro_items"
OWNER = "smartadmin"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("item", sa.String(50), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("itemtype", sa.Integer(), nullable=True),
        sa.Column("desc_itemtype", sa.String(100), nullable=True),
        sa.Column("munit", sa.String(20), nullable=True),
        sa.Column("unitcost", sa.Numeric(14, 4), nullable=True),
        sa.Column("listprice", sa.Numeric(14, 4), nullable=True),
        sa.Column("servclas", sa.Integer(), nullable=True),
        sa.Column("desc_servclas", sa.String(150), nullable=True),
        sa.Column("vida_util", sa.Numeric(14, 2), nullable=True),
        sa.Column("division_cod", sa.Integer(), nullable=True),
        sa.Column("division_desc", sa.String(100), nullable=True),
        sa.Column("macrofam_cod", sa.Integer(), nullable=True),
        sa.Column("macrofam_desc", sa.String(100), nullable=True),
        sa.Column("familia_cod", sa.Integer(), nullable=True),
        sa.Column("familia_desc", sa.String(150), nullable=True),
        sa.Column("subfamilia_cod", sa.Integer(), nullable=True),
        sa.Column("subfamilia_desc", sa.String(150), nullable=True),
        sa.Column("cod_jerarq_nivel3", sa.Numeric(14, 0), nullable=True),
        sa.Column("des_jerar_nivel3", sa.String(150), nullable=True),
        sa.Column("cod_jerarq_nivel4", sa.Numeric(14, 0), nullable=True),
        sa.Column("des_jerar_nivel4", sa.String(150), nullable=True),
        sa.Column("cod_jerarq_nivel5", sa.Numeric(14, 0), nullable=True),
        sa.Column("des_jerar_nivel5", sa.String(150), nullable=True),
        sa.Column("cod_jerarq_nivel6", sa.Numeric(14, 0), nullable=True),
        sa.Column("des_jerar_nivel6", sa.String(150), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(f'ALTER TABLE "{SCHEMA}"."{TABLE}" OWNER TO "{OWNER}"')
    )


def downgrade() -> None:
    op.drop_table(TABLE, schema=SCHEMA)
