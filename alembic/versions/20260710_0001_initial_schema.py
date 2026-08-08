"""Create the complete initial Smart Retail schema.

Revision ID: 20260710_0001
Revises:
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
HISTORICAL_TABLE = "lacteos_ventas_historicas"
PROMOTIONS_TABLE = "g2_lacteos_promociones_vigentes"
PROMOTIONS_VIEW = "vst_promociones_vigentes"
INVENTORY_TABLE = "g2_maestro_inventario_lacteos"
FORECAST_TABLE = "pronostico"
SUGGESTED_ORDER_TABLE = "pedido_sugerido"
OWNER = "smartadmin"


def set_table_owner(table: str) -> None:
    op.execute(
        sa.text(f'ALTER TABLE "{SCHEMA}"."{table}" OWNER TO "{OWNER}"')
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    import_status = postgresql.ENUM(
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        name="import_status",
        create_type=False,
    )
    import_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("destination_schema", sa.String(length=128), nullable=False),
        sa.Column("destination_table", sa.String(length=128), nullable=False),
        sa.Column("status", import_status, nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("inserted_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"], unique=False)
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"], unique=False)

    op.create_table(
        HISTORICAL_TABLE,
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column("item", sa.String(length=50), nullable=True),
        sa.Column("descripcion_item", sa.Text(), nullable=True),
        sa.Column("location", sa.Integer(), nullable=True),
        sa.Column("descripcion_tienda", sa.String(length=150), nullable=True),
        sa.Column("tipo_centro", sa.String(length=100), nullable=True),
        sa.Column("qty_vendida", sa.Numeric(precision=14, scale=2), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        PROMOTIONS_TABLE,
        sa.Column("item", sa.String(length=50), nullable=True),
        sa.Column("item_desc", sa.String(length=60), nullable=True),
        sa.Column("event_code", sa.String(length=51), nullable=True),
        sa.Column("event_name", sa.String(length=68), nullable=True),
        sa.Column("promo_mechanic", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("inicio", sa.Date(), nullable=True),
        sa.Column("fin", sa.Date(), nullable=True),
        sa.Column("desc_pct", sa.Numeric(18, 4), nullable=True),
        sa.Column("price_reg", sa.Text(), nullable=True),
        sa.Column("price_promo", sa.Text(), nullable=True),
        sa.Column("uplift_esperado", sa.Numeric(18, 4), nullable=True),
        sa.Column("dias_restantes", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        INVENTORY_TABLE,
        sa.Column("item_code", sa.String(50), nullable=True),
        sa.Column("description_item_code", sa.String(60), nullable=True),
        sa.Column("proveedor_code", sa.String(50), nullable=True),
        sa.Column("description_proveedor", sa.String(67), nullable=True),
        sa.Column("macrofamily_code", sa.String(50), nullable=True),
        sa.Column("description_macrofamily_code", sa.String(50), nullable=True),
        sa.Column("familia_code", sa.String(50), nullable=True),
        sa.Column("description_familia", sa.String(50), nullable=True),
        sa.Column("description_subagrupacion", sa.String(50), nullable=True),
        sa.Column("location_code", sa.String(50), nullable=True),
        sa.Column("description_location_code", sa.String(50), nullable=True),
        sa.Column("item_type", sa.String(50), nullable=True),
        sa.Column("estado_articulo", sa.String(50), nullable=True),
        sa.Column("temporal_freeattr5", sa.String(50), nullable=True),
        sa.Column("control_type", sa.String(50), nullable=True),
        sa.Column("estado_planificacion", sa.String(50), nullable=True),
        sa.Column("logistic_class_code", sa.String(50), nullable=True),
        sa.Column("abc_cadena", sa.String(50), nullable=True),
        sa.Column("service_level", sa.Numeric(18, 4), nullable=True),
        sa.Column("frecuencia_pedido", sa.String(50), nullable=True),
        sa.Column(
            "minimum_handling_quantity_units",
            sa.Numeric(18, 4),
            nullable=True,
        ),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("review_period_days", sa.Integer(), nullable=True),
        sa.Column("current_stock_units", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "expected_demand_qty_period_direct_sales_units_day",
            sa.Numeric(18, 4),
            nullable=True,
        ),
        sa.Column("cobertura", sa.Numeric(18, 4), nullable=True),
        sa.Column("on_order_in_transit_units", sa.Numeric(18, 4), nullable=True),
        sa.Column("extra_visibilidad_units", sa.Integer(), nullable=True),
        sa.Column("item_birth_day_date", sa.Date(), nullable=True),
        sa.Column("overstock_units", sa.Integer(), nullable=True),
        sa.Column("cantidad_ultimo_ingreso", sa.Numeric(18, 4), nullable=True),
        sa.Column("fecha_ultimo_ingreso", sa.Date(), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        FORECAST_TABLE,
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

    op.create_table(
        SUGGESTED_ORDER_TABLE,
        sa.Column("item", sa.String(50), nullable=False),
        sa.Column("location", sa.Integer(), nullable=False),
        sa.Column("descripcion_tienda", sa.String(50), nullable=False),
        sa.Column("prediccion", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("review_period_days", sa.Integer(), nullable=False),
        sa.Column("uplift_esperado", sa.Numeric(18, 4), nullable=False),
        sa.Column("minimum_handling_quantity_units", sa.Integer(), nullable=False),
        sa.Column("current_stock_units", sa.Integer(), nullable=False),
        sa.Column("on_order_in_transit_units", sa.Integer(), nullable=False),
        schema=SCHEMA,
    )

    set_table_owner(HISTORICAL_TABLE)
    set_table_owner(PROMOTIONS_TABLE)
    set_table_owner(INVENTORY_TABLE)
    set_table_owner(FORECAST_TABLE)
    set_table_owner(SUGGESTED_ORDER_TABLE)

    op.execute(
        sa.text(
            f"""
            CREATE VIEW "{SCHEMA}"."{PROMOTIONS_VIEW}" AS
            SELECT
                item,
                item_desc,
                promo_mechanic,
                status,
                MAX(inicio) AS inicio,
                MAX(fin) AS fin,
                MAX(uplift_esperado) AS uplift_esperado
            FROM "{SCHEMA}"."{PROMOTIONS_TABLE}"
            GROUP BY item, item_desc, promo_mechanic, status
            """
        )
    )
    op.execute(
        sa.text(
            f'ALTER VIEW "{SCHEMA}"."{PROMOTIONS_VIEW}" OWNER TO "{OWNER}"'
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f'DROP VIEW "{SCHEMA}"."{PROMOTIONS_VIEW}"'))
    op.drop_table(SUGGESTED_ORDER_TABLE, schema=SCHEMA)
    op.drop_table(FORECAST_TABLE, schema=SCHEMA)
    op.drop_table(INVENTORY_TABLE, schema=SCHEMA)
    op.drop_table(PROMOTIONS_TABLE, schema=SCHEMA)
    op.drop_table(HISTORICAL_TABLE, schema=SCHEMA)
    op.drop_index("ix_import_jobs_user_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_table("import_jobs")

    import_status = postgresql.ENUM(
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        name="import_status",
    )
    import_status.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
