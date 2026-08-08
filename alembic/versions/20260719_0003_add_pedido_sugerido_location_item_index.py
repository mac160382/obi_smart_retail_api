"""Add the suggested-order location and item index.

Revision ID: 20260719_0003
Revises: 20260718_0002
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260719_0003"
down_revision: Union[str, None] = "20260718_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pedido_sugerido"
INDEX = "ix_pedido_sugerido_location_item"


def upgrade() -> None:
    op.create_index(
        INDEX,
        TABLE,
        ["location", "item"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA)
