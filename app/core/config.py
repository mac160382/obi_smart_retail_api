from datetime import date
from functools import lru_cache
from pathlib import Path

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
    rabbitmq_queue: str = "jaimito"
    rabbitmq_historical_sales_routing_key: str = "historical_sales.imported"
    rabbitmq_forecast_loaded_queue: str = "smart_retail.forecast.loaded"
    rabbitmq_forecast_loaded_routing_key: str = "forecast.loaded"
    rabbitmq_publish_timeout_seconds: float = Field(default=10, gt=0, le=60)

    sse_heartbeat_seconds: int = Field(default=15, ge=5, le=60)
    sse_client_queue_size: int = Field(default=100, ge=1, le=1000)
    sse_replay_limit: int = Field(default=1000, ge=1, le=10_000)

    max_upload_size_mb: int = 20
    csv_encoding: str = "utf-8-sig"
    csv_delimiter: str = ","
    csv_batch_size: int = Field(default=1000, ge=1, le=50_000)

    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    assistant_enabled: bool = False
    assistant_real_llm_enabled: bool = False
    assistant_enabled_tools: str = (
        "consultar_pedidos_sugeridos,consultar_pronosticos,consultar_articulos,"
        "consultar_tiendas,consultar_ventas,consultar_inventario,consultar_parametros,"
        "consultar_promociones,consultar_ejecuciones,consultar_metricas_modelo,"
        "consultar_shap_global,consultar_shap_horizontes,consultar_shap_local"
    )
    assistant_max_records: int = Field(default=25, ge=1, le=100)
    assistant_max_tool_calls: int = Field(default=6, ge=1, le=20)
    assistant_max_model_calls: int = Field(default=4, ge=2, le=10)
    assistant_default_forecast_origin: date | None = None
    assistant_artifact_dir: Path = Path("resources/artifacts")
    assistant_execution_dir: Path = Path("resources/executions")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def assistant_enabled_tool_names(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                name.strip() for name in self.assistant_enabled_tools.split(",") if name.strip()
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
