"""Add descriptions and status to pedido_sugerido.

Revision ID: 20260719_0004
Revises: 20260719_0003
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0004"
down_revision: Union[str, None] = "20260719_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
TABLE = "pedido_sugerido"
STATUS_TYPE = "pedido_sugerido_status"


def upgrade() -> None:
    status_type = postgresql.ENUM(
        "Estimado",
        "Planificado",
        "Aprobado",
        name=STATUS_TYPE,
        create_type=False,
    )
    status_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        TABLE,
        sa.Column(
            "descripcion_item",
            sa.String(60),
            server_default=sa.text("''"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "descripcion_proveedor",
            sa.String(67),
            server_default=sa.text("''"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "status",
            status_type,
            server_default=sa.text("'Estimado'"),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    op.alter_column(
        TABLE,
        "descripcion_item",
        existing_type=sa.String(60),
        existing_nullable=False,
        server_default=None,
        schema=SCHEMA,
    )
    op.alter_column(
        TABLE,
        "descripcion_proveedor",
        existing_type=sa.String(67),
        existing_nullable=False,
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "status", schema=SCHEMA)
    op.drop_column(TABLE, "descripcion_proveedor", schema=SCHEMA)
    op.drop_column(TABLE, "descripcion_item", schema=SCHEMA)

    status_type = postgresql.ENUM(
        "Estimado",
        "Planificado",
        "Aprobado",
        name=STATUS_TYPE,
    )
    status_type.drop(op.get_bind(), checkfirst=True)
