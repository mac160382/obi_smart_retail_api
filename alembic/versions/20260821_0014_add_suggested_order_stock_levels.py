"""Add stock level fields to suggested orders.

Revision ID: 20260821_0014
Revises: 20260821_0013
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0014"
down_revision: str | None = "20260821_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
TABLE = "pedido_sugerido"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "max_qty_vendida",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "safety_stock",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "reorder_point",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "reorder_point", schema=SCHEMA)
    op.drop_column(TABLE, "safety_stock", schema=SCHEMA)
    op.drop_column(TABLE, "max_qty_vendida", schema=SCHEMA)
