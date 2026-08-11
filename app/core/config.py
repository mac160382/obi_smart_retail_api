from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Retail Lácteos API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str
    database_schema: str = "public"
    historical_sales_table: str = "lacteos_ventas_historicas"
    current_promotions_schema: str = "public"
    current_promotions_table: str = "g2_lacteos_promociones_vigentes"
    current_promotions_view_schema: str = "public"
    current_promotions_view: str = "vst_promociones_vigentes"
    inventory_master_schema: str = "public"
    inventory_master_table: str = "g2_maestro_inventario_lacteos"
    items_master_schema: str = "public"
    items_master_table: str = "lacteos_maestro_items"
    stores_master_schema: str = "public"
    stores_master_table: str = "lacteos_maestro_tiendas"
    forecast_schema: str = "public"
    forecast_table: str = "pronostico"
    suggested_orders_schema: str = "public"
    suggested_orders_table: str = "pedido_sugerido"
    database_owner: str = "smartadmin"

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    cors_origins: list[str] = []

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = Field(default=5672, ge=1, le=65_535)
    rabbitmq_user: str = Field(min_length=1)
    rabbitmq_password: str = Field(min_length=12)
    rabbitmq_virtual_host: str = "smart_retail"
    rabbitmq_exchange: str = "smart_retail.events"

    max_upload_size_mb: int = 20
    csv_encoding: str = "utf-8-sig"
    csv_delimiter: str = ","
    csv_batch_size: int = Field(default=1000, ge=1, le=50_000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
