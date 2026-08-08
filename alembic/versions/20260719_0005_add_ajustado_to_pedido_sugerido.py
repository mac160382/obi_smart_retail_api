"""Add ajustado to pedido_sugerido.

Revision ID: 20260719_0005
Revises: 20260719_0004
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0005"
down_revision: Union[str, None] = "20260719_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pedido_sugerido"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "ajustado",
            postgresql.DOUBLE_PRECISION(),
            nullable=True,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "ajustado", schema=SCHEMA)
