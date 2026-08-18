"""Add suggested-order approvals, logical key and history.

Revision ID: 20260817_0011
Revises: 20260811_0010
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260817_0011"
down_revision: str | None = "20260811_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"
ORDERS_TABLE = "pedido_sugerido"
HISTORY_TABLE = "pedido_sugerido_historial"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM "{SCHEMA}"."{ORDERS_TABLE}"
                    GROUP BY item, location, forecast_origin, horizon_day
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'No se puede crear la llave logica de pedido_sugerido: existen duplicados';
                END IF;
            END
            $$;
            """
        )
    )

    op.add_column(
        ORDERS_TABLE,
        sa.Column("observaciones", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        ORDERS_TABLE,
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        ORDERS_TABLE,
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        ORDERS_TABLE,
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_pedido_sugerido_logical_key",
        ORDERS_TABLE,
        ["item", "location", "forecast_origin", "horizon_day"],
        schema=SCHEMA,
    )

    op.create_table(
        HISTORY_TABLE,
        sa.Column(
            "change_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("item", sa.String(length=50), nullable=False),
        sa.Column("location", sa.Integer(), nullable=False),
        sa.Column("forecast_origin", sa.Date(), nullable=False),
        sa.Column("horizon_day", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("ajustado_anterior", sa.Float(), nullable=True),
        sa.Column("ajustado_nuevo", sa.Float(), nullable=False),
        sa.Column("observaciones_anteriores", sa.Text(), nullable=True),
        sa.Column("observaciones_nuevas", sa.Text(), nullable=False),
        sa.Column("status_anterior", sa.String(length=20), nullable=False),
        sa.Column("status_nuevo", sa.String(length=20), nullable=False),
        sa.Column(
            "modified_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("change_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pedido_sugerido_historial_logical_key",
        HISTORY_TABLE,
        ["item", "location", "forecast_origin", "horizon_day"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pedido_sugerido_historial_batch_id",
        HISTORY_TABLE,
        ["batch_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pedido_sugerido_historial_batch_id",
        table_name=HISTORY_TABLE,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_pedido_sugerido_historial_logical_key",
        table_name=HISTORY_TABLE,
        schema=SCHEMA,
    )
    op.drop_table(HISTORY_TABLE, schema=SCHEMA)
    op.drop_constraint(
        "uq_pedido_sugerido_logical_key",
        ORDERS_TABLE,
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_column(ORDERS_TABLE, "updated_at", schema=SCHEMA)
    op.drop_column(ORDERS_TABLE, "approved_at", schema=SCHEMA)
    op.drop_column(ORDERS_TABLE, "approved_by", schema=SCHEMA)
    op.drop_column(ORDERS_TABLE, "observaciones", schema=SCHEMA)
