"""Make suggested-order approval observations optional.

Revision ID: 20260819_0012
Revises: 20260817_0011
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260819_0012"
down_revision: str | None = "20260817_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
HISTORY_TABLE = "pedido_sugerido_historial"


def upgrade() -> None:
    op.alter_column(
        HISTORY_TABLE,
        "observaciones_nuevas",
        existing_type=sa.Text(),
        nullable=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE "{SCHEMA}"."{HISTORY_TABLE}"
            SET observaciones_nuevas = ''
            WHERE observaciones_nuevas IS NULL
            """
        )
    )
    op.alter_column(
        HISTORY_TABLE,
        "observaciones_nuevas",
        existing_type=sa.Text(),
        nullable=False,
        schema=SCHEMA,
    )
