"""Add sugerido to pedido_sugerido.

Revision ID: 20260718_0002
Revises: 20260710_0001
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260718_0002"
down_revision: Union[str, None] = "20260710_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pedido_sugerido"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "sugerido",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.alter_column(
        TABLE,
        "sugerido",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "sugerido", schema=SCHEMA)
