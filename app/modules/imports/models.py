import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import (
    DOUBLE_PRECISION,
    JSONB,
)
from sqlalchemy.dialects.postgresql import (
    ENUM as PGEnum,
)
from sqlalchemy.dialects.postgresql import (
    UUID as PGUUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base


class ImportStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_schema: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_table: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status"),
        default=ImportStatus.PROCESSING,
        index=True,
        nullable=False,
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    columns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


# La tabla de negocio no tiene clave primaria; por eso se define con SQLAlchemy Core.
business_metadata = MetaData()

lacteos_ventas_historicas = Table(
    settings.historical_sales_table,
    business_metadata,
    Column("fecha", Date, nullable=True),
    Column("item", String(50), nullable=True),
    Column("descripcion_item", Text, nullable=True),
    Column("location", Integer, nullable=True),
    Column("descripcion_tienda", String(150), nullable=True),
    Column("tipo_centro", String(100), nullable=True),
    Column("qty_vendida", Numeric(14, 2), nullable=True),
    schema=settings.database_schema,
)

g2_lacteos_promociones_vigentes = Table(
    settings.current_promotions_table,
    business_metadata,
    Column("item", String(50), nullable=True),
    Column("item_desc", String(60), nullable=True),
    Column("event_code", String(51), nullable=True),
    Column("event_name", String(68), nullable=True),
    Column("promo_mechanic", String(50), nullable=True),
    Column("status", String(50), nullable=True),
    Column("inicio", Date, nullable=True),
    Column("fin", Date, nullable=True),
    Column("desc_pct", Numeric(18, 4), nullable=True),
    Column("price_reg", Text, nullable=True),
    Column("price_promo", Text, nullable=True),
    Column("uplift_esperado", Numeric(18, 4), nullable=True),
    Column("dias_restantes", Integer, nullable=True),
    schema=settings.current_promotions_schema,
)

g2_maestro_inventario_lacteos = Table(
    settings.inventory_master_table,
    business_metadata,
    Column("item_code", String(50), nullable=True),
    Column("description_item_code", String(60), nullable=True),
    Column("proveedor_code", String(50), nullable=True),
    Column("description_proveedor", String(67), nullable=True),
    Column("macrofamily_code", String(50), nullable=True),
    Column("description_macrofamily_code", String(50), nullable=True),
    Column("familia_code", String(50), nullable=True),
    Column("description_familia", String(50), nullable=True),
    Column("description_subagrupacion", String(50), nullable=True),
    Column("location_code", String(50), nullable=True),
    Column("description_location_code", String(50), nullable=True),
    Column("item_type", String(50), nullable=True),
    Column("estado_articulo", String(50), nullable=True),
    Column("temporal_freeattr5", String(50), nullable=True),
    Column("control_type", String(50), nullable=True),
    Column("estado_planificacion", String(50), nullable=True),
    Column("logistic_class_code", String(50), nullable=True),
    Column("abc_cadena", String(50), nullable=True),
    Column("service_level", Numeric(18, 4), nullable=True),
    Column("frecuencia_pedido", String(50), nullable=True),
    Column("minimum_handling_quantity_units", Numeric(18, 4), nullable=True),
    Column("lead_time_days", Integer, nullable=True),
    Column("review_period_days", Integer, nullable=True),
    Column("current_stock_units", Numeric(18, 4), nullable=True),
    Column(
        "expected_demand_qty_period_direct_sales_units_day",
        Numeric(18, 4),
        nullable=True,
    ),
    Column("cobertura", Numeric(18, 4), nullable=True),
    Column("on_order_in_transit_units", Numeric(18, 4), nullable=True),
    Column("extra_visibilidad_units", Integer, nullable=True),
    Column("item_birth_day_date", Date, nullable=True),
    Column("overstock_units", Integer, nullable=True),
    Column("cantidad_ultimo_ingreso", Numeric(18, 4), nullable=True),
    Column("fecha_ultimo_ingreso", Date, nullable=True),
    schema=settings.inventory_master_schema,
)

lacteos_maestro_items = Table(
    settings.items_master_table,
    business_metadata,
    Column("item", String(50), nullable=True),
    Column("descripcion", Text, nullable=True),
    Column("itemtype", Integer, nullable=True),
    Column("desc_itemtype", String(100), nullable=True),
    Column("munit", String(20), nullable=True),
    Column("unitcost", Numeric(14, 4), nullable=True),
    Column("listprice", Numeric(14, 4), nullable=True),
    Column("servclas", Integer, nullable=True),
    Column("desc_servclas", String(150), nullable=True),
    Column("vida_util", Numeric(14, 2), nullable=True),
    Column("division_cod", Integer, nullable=True),
    Column("division_desc", String(100), nullable=True),
    Column("macrofam_cod", Integer, nullable=True),
    Column("macrofam_desc", String(100), nullable=True),
    Column("familia_cod", Integer, nullable=True),
    Column("familia_desc", String(150), nullable=True),
    Column("subfamilia_cod", Integer, nullable=True),
    Column("subfamilia_desc", String(150), nullable=True),
    Column("cod_jerarq_nivel3", Numeric(14, 0), nullable=True),
    Column("des_jerar_nivel3", String(150), nullable=True),
    Column("cod_jerarq_nivel4", Numeric(14, 0), nullable=True),
    Column("des_jerar_nivel4", String(150), nullable=True),
    Column("cod_jerarq_nivel5", Numeric(14, 0), nullable=True),
    Column("des_jerar_nivel5", String(150), nullable=True),
    Column("cod_jerarq_nivel6", Numeric(14, 0), nullable=True),
    Column("des_jerar_nivel6", String(150), nullable=True),
    schema=settings.items_master_schema,
)

lacteos_maestro_tiendas = Table(
    settings.stores_master_table,
    business_metadata,
    Column("location", Integer, nullable=True),
    Column("descripcion", String(150), nullable=True),
    Column("tipo_centro", String(100), nullable=True),
    Column("region", String(100), nullable=True),
    Column("estado", Integer, nullable=True),
    Column("sociedad", Integer, nullable=True),
    schema=settings.stores_master_schema,
)

pronostico = Table(
    settings.forecast_table,
    business_metadata,
    Column("forecast_origin", Date, nullable=True),
    Column("target_date", Date, nullable=True),
    Column("horizon_day", Integer, nullable=True),
    Column("descripcion_item", Text, nullable=True),
    Column("item", String(50), nullable=True),
    Column("item_code", Integer, nullable=True),
    Column("descripcion_tienda", String(150), nullable=True),
    Column("location", Integer, nullable=True),
    Column("location_code", Integer, nullable=True),
    Column("forecast_qty_vendida", DOUBLE_PRECISION, nullable=True),
    Column("raw_prediction", DOUBLE_PRECISION, nullable=True),
    Column("was_clipped_to_zero", Boolean, nullable=True),
    Column("unknown_item", Boolean, nullable=True),
    Column("unknown_location", Boolean, nullable=True),
    Column("history_days", Integer, nullable=True),
    Column("model_key", String(100), nullable=True),
    Column("model_name", String(150), nullable=True),
    Column("model_cutoff", Date, nullable=True),
    Column("generated_utc", DateTime(timezone=True), nullable=True),
    schema=settings.forecast_schema,
)

vst_promociones_vigentes = Table(
    settings.current_promotions_view,
    business_metadata,
    Column("item", String(50), nullable=True),
    Column("uplift_esperado", Numeric(18, 4), nullable=True),
    schema=settings.current_promotions_view_schema,
)

pedido_sugerido = Table(
    settings.suggested_orders_table,
    business_metadata,
    Column("item", String(50), nullable=False),
    Column("forecast_origin", Date, nullable=False),
    Column("horizon_day", Integer, nullable=False),
    Column("target_date", Date, nullable=False),
    Column("location", Integer, nullable=False),
    Column("descripcion_tienda", String(50), nullable=False),
    Column("prediccion", DOUBLE_PRECISION, nullable=False),
    Column("ajustado", DOUBLE_PRECISION, nullable=True),
    Column("observaciones", Text, nullable=True),
    Column("approved_by", PGUUID(as_uuid=True), nullable=True),
    Column("approved_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=True),
    Column("lead_time_days", Integer, nullable=False),
    Column("review_period_days", Integer, nullable=False),
    Column("uplift_esperado", Numeric(18, 4), nullable=False),
    Column("minimum_handling_quantity_units", Integer, nullable=False),
    Column("current_stock_units", Integer, nullable=False),
    Column("on_order_in_transit_units", Integer, nullable=False),
    Column("sugerido", Integer, nullable=False),
    Column("descripcion_item", String(60), nullable=False),
    Column("descripcion_proveedor", String(67), nullable=False),
    Column(
        "status",
        PGEnum(
            "Estimado",
            "Planificado",
            "Aprobado",
            name="pedido_sugerido_status",
            create_type=False,
        ),
        server_default="Estimado",
        nullable=False,
    ),
    UniqueConstraint(
        "item",
        "location",
        "forecast_origin",
        "horizon_day",
        name="uq_pedido_sugerido_logical_key",
    ),
    schema=settings.suggested_orders_schema,
)

pedido_sugerido_historial = Table(
    "pedido_sugerido_historial",
    business_metadata,
    Column("change_id", PGUUID(as_uuid=True), primary_key=True),
    Column("batch_id", PGUUID(as_uuid=True), nullable=False),
    Column("item", String(50), nullable=False),
    Column("location", Integer, nullable=False),
    Column("forecast_origin", Date, nullable=False),
    Column("horizon_day", Integer, nullable=False),
    Column("target_date", Date, nullable=False),
    Column("ajustado_anterior", DOUBLE_PRECISION, nullable=True),
    Column("ajustado_nuevo", DOUBLE_PRECISION, nullable=False),
    Column("observaciones_anteriores", Text, nullable=True),
    Column("observaciones_nuevas", Text, nullable=True),
    Column("status_anterior", String(20), nullable=False),
    Column("status_nuevo", String(20), nullable=False),
    Column("modified_by", PGUUID(as_uuid=True), nullable=False),
    Column("modified_at", DateTime(timezone=True), nullable=False),
    schema=settings.suggested_orders_schema,
)
