# FastAPI + PostgreSQL: monolito modular para ventas históricas de lácteos

El proyecto carga archivos CSV en:

```text
public.lacteos_ventas_historicas
```

La tabla de negocio respeta esta estructura:

```sql
CREATE TABLE IF NOT EXISTS public.lacteos_ventas_historicas
(
    fecha date,
    item character varying(50),
    descripcion_item text,
    location integer,
    descripcion_tienda character varying(150),
    tipo_centro character varying(100),
    qty_vendida numeric(14,2)
);
```

## Decisión de diseño

La tabla no tiene clave primaria. Para no modificar su contrato, se define con
SQLAlchemy Core en `app/modules/imports/models.py`. Las tablas técnicas `users`
e `import_jobs` sí se manejan con ORM.

## Inicio

```bash
cp .env.example .env
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -e ".[dev]"
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

## Ejecutar API y PostgreSQL con Docker

### Requisitos

- Docker Desktop o Docker Engine con Docker Compose v2.
- Puertos `8000` y `5432` disponibles.

### 1. Crear la configuración local

Desde la raíz del proyecto, copiar el archivo de ejemplo:

Linux o macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Antes de compartir o desplegar el proyecto, reemplazar `JWT_SECRET_KEY` y las
credenciales de PostgreSQL por valores seguros. No subir `.env` al repositorio.

### 2. Construir e iniciar los servicios

```bash
docker compose up -d --build
```

Este comando inicia:

- PostgreSQL en `localhost:5432`.
- RabbitMQ en `localhost:5672` y su consola de administración en
  `http://localhost:15672`.
- La API en `http://localhost:8000`.
- Las migraciones de Alembic mediante `alembic upgrade head` antes de iniciar
  Uvicorn.

### 3. Verificar el estado

```bash
docker compose ps
curl http://localhost:8000/health
```

La respuesta esperada del health check es:

```json
{"status":"ok"}
```

La documentación OpenAPI está disponible en
`http://localhost:8000/docs` cuando `APP_ENV` no es `production`.

### Consultar logs

```bash
docker compose logs -f api
docker compose logs -f db
docker compose logs -f rabbitmq
```

### Reconstruir solamente la API

```bash
docker compose up -d --build api
```

### Conectarse a PostgreSQL desde el contenedor

```bash
docker compose exec db psql -U smartadmin -d smart_retail
```

### Detener el proyecto

Conservar los datos de PostgreSQL:

```bash
docker compose down
```

Eliminar también el volumen y todos los datos:

```bash
docker compose down -v
```

## RabbitMQ

Docker crea un broker RabbitMQ `4.3.4-management-alpine` independiente con:

- Vhost: `smart_retail`.
- Exchange durable tipo `topic`: `smart_retail.events`.
- Volumen persistente: `rabbitmq_data`.
- Health check mediante `rabbitmq-diagnostics`.

Al iniciar, FastAPI establece una conexión robusta y declara el exchange. Esta
inicialización no publica mensajes.

El usuario, la contraseña, el vhost y el exchange se configuran en `.env` con
las variables `RABBITMQ_USER`, `RABBITMQ_PASSWORD`,
`RABBITMQ_VIRTUAL_HOST` y `RABBITMQ_EXCHANGE`. Las credenciales de ejemplo deben
reemplazarse antes de utilizar el proyecto fuera de un entorno local.

La consola se abre en `http://localhost:15672`. Para verificar el broker desde
el contenedor:

```bash
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
docker compose exec rabbitmq rabbitmqctl list_vhosts
docker compose exec rabbitmq rabbitmqctl list_exchanges -p smart_retail name type durable
```

La API incluye un publicador con mensajes JSON persistentes, publisher confirms
y conexión robusta. Al iniciar declara la cola durable `jaimito` y la enlaza al
exchange con la routing key `historical_sales.imported`.

La API tambien declara y consume la cola durable
`smart_retail.forecast.loaded`, enlazada al mismo exchange con la routing key
`forecast.loaded`. El evento debe usar el sobre JSON de eventos de la API,
tener `event_type=forecast.loaded`, `event_version=1`, un `event_id` UUID y ser
un mensaje persistente. Cuando se recibe correctamente, el consumidor ejecuta
el mismo servicio interno utilizado por
`POST /api/v1/suggested-orders/recalculate`; no realiza una llamada HTTP al
propio API. El mensaje se confirma manualmente solamente despues del commit del
recalculo. Un evento invalido se rechaza, una ejecucion concurrente se reencola
y un error inesperado se reintenta una vez.

El consumidor toma `data.forecast_origin`, lo convierte a `date` y lo pasa al
repositorio como filtro del `INSERT` de `public.pedido_sugerido`.

### Eventos SSE de pedido sugerido

Una vez confirmado el recÃ¡lculo originado por `forecast.loaded`, la API guarda
la notificaciÃ³n en PostgreSQL y la transmite por:

```text
GET /api/v1/suggested-orders/events
```

El endpoint requiere el mismo token OAuth2 Bearer que el resto de la API y
responde como `text/event-stream`. El token no debe enviarse en la URL. Como
`EventSource` nativo no permite establecer `Authorization`, el frontend React
debe utilizar `fetch` con streaming o una biblioteca SSE que acepte encabezados:

```javascript
const response = await fetch(
  "http://localhost:8000/api/v1/suggested-orders/events",
  {
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${accessToken}`,
    },
  },
);
```

Para probar la conexiÃ³n desde una terminal:

```bash
curl -N http://localhost:8000/api/v1/suggested-orders/events \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

El evento emitido se llama `suggested-orders.recalculated` e incluye el estado,
identificador del evento `forecast.loaded`, `forecast_origin`, filas eliminadas
e insertadas, duraciÃ³n y fecha del cÃ¡lculo. `forecast_origin` debe llegar en
`data` del evento `forecast.loaded` con formato `YYYY-MM-DD`; si falta o es
invÃ¡lido, el mensaje se rechaza sin ejecutar el recÃ¡lculo. La API envÃ­a
keep-alives, cierra la conexiÃ³n al expirar el JWT y acepta `Last-Event-ID` para
recuperar eventos persistidos tras una desconexiÃ³n.

## Registrar usuario

```bash
curl -X POST http://localhost:8000/api/v1/auth/register   -H "Content-Type: application/json"   -d '{"username":"admin","email":"admin@example.com","password":"Password123"}'
```

## Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login   -H "Content-Type: application/x-www-form-urlencoded"   -d "username=admin&password=Password123"
```

## Cargar ventas históricas

El campo `mode` es obligatorio. `publish_message` es opcional y utiliza `false`
como valor predeterminado. Cuando `publish_message=true`, `fecha` se vuelve
obligatoria, utiliza el formato `YYYY-MM-DD` y debe coincidir con la columna
`fecha` de todas las filas del CSV. Si alguna fecha es diferente, vacía o
inválida, se rechaza el archivo completo con `422 Unprocessable Entity` y no se
modifica la información existente.

Cuando `publish_message=false`, `fecha` puede omitirse y no se realiza la
comparación entre el parámetro y las fechas del CSV. Cuando es `true`, después
del commit se publica en `jaimito` un evento `historical_sales.imported` que
incluye `fecha`, `mode`, nombre del archivo, conteos y tabla destino.

La respuesta incluye `message_publication_status`, con uno de estos valores:

- `not_requested`: no se solicitó publicación.
- `published`: RabbitMQ confirmó el mensaje.
- `failed`: la carga quedó confirmada en PostgreSQL, pero RabbitMQ no confirmó
  el mensaje dentro del tiempo configurado.

El identificador `message_event_id` coincide con el identificador del trabajo de
importación para facilitar la deduplicación en los consumidores.

`mode` admite:

- `incremental`: agrega los registros y, después del `commit`, programa el mock
  de feature engineering con las filas válidas recibidas.
- `replace`: elimina los registros actuales y carga los nuevos dentro de una
  sola transacción. No ejecuta feature engineering.

Carga incremental:

```bash
curl -X POST http://localhost:8000/api/v1/imports/historical-sales/csv   -H "Authorization: Bearer REEMPLAZAR_TOKEN"   -F "file=@sample_lacteos_ventas_historicas.csv"   -F "mode=incremental"   -F "publish_message=false"
```

Reemplazo completo:

```bash
curl -X POST http://localhost:8000/api/v1/imports/historical-sales/csv   -H "Authorization: Bearer REEMPLAZAR_TOKEN"   -F "file=@sample_lacteos_ventas_historicas.csv"   -F "mode=replace"   -F "publish_message=true"   -F "fecha=2026-08-10"
```

## Columnas CSV

El encabezado debe contener exactamente:

```text
fecha,item,descripcion_item,location,descripcion_tienda,tipo_centro,qty_vendida
```

Formatos:

- `fecha`: `YYYY-MM-DD` o `DD/MM/YYYY`.
- `item`: máximo 50 caracteres.
- `location`: entero.
- `descripcion_tienda`: máximo 150 caracteres.
- `tipo_centro`: máximo 100 caracteres.
- `qty_vendida`: decimal compatible con `NUMERIC(14,2)`.
- Todos los campos de la tabla permiten valores vacíos, que se convierten a `NULL`.

## Cargar promociones vigentes

Este endpoint reemplaza de forma atómica todos los registros de
`public.g2_lacteos_promociones_vigentes`:

```bash
curl -X POST http://localhost:8000/api/v1/imports/current-promotions/csv   -H "Authorization: Bearer REEMPLAZAR_TOKEN"   -F "file=@promociones.csv"
```

El encabezado debe contener exactamente:

```text
item,item_desc,event_code,event_name,promo_mechanic,status,inicio,fin,desc_pct,price_reg,price_promo,uplift_esperado,dias_restantes
```

`inicio` y `fin` admiten `YYYY-MM-DD` o `DD/MM/YYYY`. `desc_pct` y
`uplift_esperado` admiten un máximo de cuatro decimales. Si cualquier fila es
inválida, se rechaza todo el archivo y los registros existentes no se modifican.

La vista `public.vst_promociones_vigentes` resume las promociones agrupando por
`item`, `item_desc`, `promo_mechanic` y `status`, y obtiene los valores máximos
de `inicio`, `fin` y `uplift_esperado`. La vista no define un orden; las consultas
que necesiten ordenamiento deben usar:

```sql
SELECT *
FROM public.vst_promociones_vigentes
ORDER BY item;
```

## Cargar maestro de inventario

Este endpoint reemplaza de forma atómica todos los registros de
`public.g2_maestro_inventario_lacteos`:

```bash
curl -X POST http://localhost:8000/api/v1/imports/inventory-master/csv   -H "Authorization: Bearer REEMPLAZAR_TOKEN"   -F "file=@inventario.csv"
```

El encabezado debe contener exactamente:

```text
item_code,description_item_code,proveedor_code,description_proveedor,macrofamily_code,description_macrofamily_code,familia_code,description_familia,description_subagrupacion,location_code,description_location_code,item_type,estado_articulo,temporal_freeattr5,control_type,estado_planificacion,logistic_class_code,abc_cadena,service_level,frecuencia_pedido,minimum_handling_quantity_units,lead_time_days,review_period_days,current_stock_units,expected_demand_qty_period_direct_sales_units_day,cobertura,on_order_in_transit_units,extra_visibilidad_units,item_birth_day_date,overstock_units,cantidad_ultimo_ingreso,fecha_ultimo_ingreso
```

Las columnas numéricas admiten un máximo de cuatro decimales y las fechas
aceptan `YYYY-MM-DD` o `DD/MM/YYYY`. Si cualquier fila es inválida, se rechaza
todo el archivo y los registros existentes no se modifican.

## Cargar maestro de artículos

Este endpoint reemplaza de forma atómica todos los registros de
`public.lacteos_maestro_items`:

```bash
curl -X POST http://localhost:8000/api/v1/imports/items-master/csv \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN" \
  -F "file=@maestro_items.csv"
```

El encabezado debe contener exactamente:

```text
item,descripcion,itemtype,desc_itemtype,munit,unitcost,listprice,servclas,desc_servclas,vida_util,division_cod,division_desc,macrofam_cod,macrofam_desc,familia_cod,familia_desc,subfamilia_cod,subfamilia_desc,cod_jerarq_nivel3,des_jerar_nivel3,cod_jerarq_nivel4,des_jerar_nivel4,cod_jerarq_nivel5,des_jerar_nivel5,cod_jerarq_nivel6,des_jerar_nivel6
```

Todos los campos permiten valores vacíos, que se convierten a `NULL`.
`unitcost` y `listprice` admiten cuatro decimales; `vida_util`, dos; y los
códigos jerárquicos de nivel 3 a 6 deben ser enteros compatibles con
`NUMERIC(14,0)`. Si cualquier fila es inválida, se rechaza todo el archivo y
los registros existentes no se modifican.

## Cargar maestro de tiendas

Este endpoint reemplaza de forma atómica todos los registros de
`public.lacteos_maestro_tiendas`:

```bash
curl -X POST http://localhost:8000/api/v1/imports/stores-master/csv \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN" \
  -F "file=@maestro_tiendas.csv"
```

El encabezado debe contener exactamente:

```text
location,descripcion,tipo_centro,region,estado,sociedad
```

`location`, `estado` y `sociedad` deben ser enteros. Todos los campos permiten
valores vacíos, que se convierten a `NULL`. Si cualquier fila es inválida, se
rechaza todo el archivo y los registros existentes no se modifican.

## Cargar pronósticos

Este endpoint reemplaza de forma atómica todos los registros de
`public.pronostico`:

```bash
curl -X POST http://localhost:8000/api/v1/imports/forecast/csv \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN" \
  -F "file=@Pronostico_template.csv"
```

El encabezado debe contener exactamente:

```text
forecast_origin,target_date,horizon_day,descripcion_item,item,item_code,descripcion_tienda,location,location_code,forecast_qty_vendida,raw_prediction,was_clipped_to_zero,unknown_item,unknown_location,history_days,model_key,model_name,model_cutoff,generated_utc
```

`forecast_origin`, `target_date` y `model_cutoff` utilizan fechas ISO
`YYYY-MM-DD`. `generated_utc` utiliza fecha-hora ISO 8601 con zona horaria. Las
banderas booleanas aceptan `True`, `False`, `1` o `0`; las predicciones se
almacenan como `double precision`. Si cualquier fila es inválida, se rechaza
todo el archivo y los datos existentes no se modifican.

La carga reemplaza únicamente los registros de `public.pronostico`. No ejecuta
el cálculo de pedidos sugeridos ni modifica `public.pedido_sugerido`; ese proceso
permanece separado en `/api/v1/suggested-orders/recalculate`.

## Vista de venta historica maxima

Alembic crea `public.vst_max_vta_historica`, que devuelve una fila por
combinacion de `item` y `location` con el valor maximo historico de
`qty_vendida`:

```sql
SELECT item, location, max_qty_vendida
FROM public.vst_max_vta_historica;
```

La vista consulta `public.lacteos_ventas_historicas` y pertenece al usuario
`smartadmin`.

## Tabla de pedido sugerido

Las migraciones crean `public.pedido_sugerido` con las siguientes columnas,
todas obligatorias y sin llave primaria:

```text
item,forecast_origin,horizon_day,target_date,location,descripcion_tienda,descripcion_item,descripcion_proveedor,prediccion,ajustado,observaciones,approved_by,approved_at,updated_at,lead_time_days,review_period_days,uplift_esperado,minimum_handling_quantity_units,current_stock_units,on_order_in_transit_units,sugerido,max_qty_vendida,safety_stock,reorder_point,status
```

`descripcion_item` utiliza `varchar(60)` y `descripcion_proveedor`, `varchar(67)`,
de acuerdo con las longitudes de las columnas fuente. `prediccion` utiliza
`double precision`; `ajustado` utiliza el mismo tipo y permite `NULL`;
`uplift_esperado`, `numeric(18,4)`; y las cantidades, periodos, `sugerido`,
`max_qty_vendida`, `safety_stock` y `reorder_point` utilizan `integer`. Estas
tres nuevas columnas tienen cero como valor predeterminado. `status` admite
`Estimado`, `Planificado` y `Aprobado`, con
`Estimado` como valor predeterminado. `forecast_origin` y `target_date` utilizan
`date`, y `horizon_day`, `integer`; las tres columnas son obligatorias.

La combinacion `item`, `location`, `forecast_origin` y `horizon_day` es unica,
aunque la tabla continua sin llave primaria. Las columnas `observaciones`,
`approved_by`, `approved_at` y `updated_at` permiten consultar la ultima
aprobacion aplicada.

## Calcular pedido sugerido

Este endpoint reemplaza de forma atómica los registros de
`public.pedido_sugerido` con el resultado calculado en PostgreSQL:

```bash
curl -X POST "http://localhost:8000/api/v1/suggested-orders/recalculate?forecast_origin=2026-06-24" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

El parámetro obligatorio `forecast_origin` utiliza el formato `YYYY-MM-DD`. El
procedimiento parte del inventario y relaciona el pronóstico mediante `item` y
`location`, pero inserta solamente los pronósticos cuya fecha de origen coincide
con el parámetro. Las promociones se relacionan por artículo y la venta histórica
máxima mediante `item` y `location`.

Las métricas de inventario se calculan así:

```text
safety_stock = CEIL(max_qty_vendida * lead_time_days
                    - prediccion * lead_time_days)

reorder_point = CEIL(lead_time_days * prediccion
                     + max_qty_vendida * lead_time_days
                     - prediccion * lead_time_days)

sugerido = CEIL(prediccion * (1 + uplift_esperado)
                + minimum_handling_quantity_units
                - current_stock_units
                - on_order_in_transit_units
                + (max_qty_vendida * lead_time_days
                   - prediccion * lead_time_days))
```

Los valores de texto nulos se sustituyen por una cadena vacía y los valores
numéricos nulos por cero. El borrado y la inserción se ejecutan en una sola
transacción; un error revierte ambos cambios y conserva el resultado anterior.
Cada recálculo obtiene `descripcion_item` de `description_item_code`,
`descripcion_proveedor` de la columna homónima del inventario e inicializa
`status` en `Estimado`. Como `ajustado` no forma parte del cálculo, queda en
`NULL` después de cada reemplazo.

El recalculo elimina solamente los registros que no estan aprobados. Los
registros con `status=Aprobado` se conservan y no se inserta otro registro con
la misma combinacion de `item`, `location`, `forecast_origin` y `horizon_day`.
Por lo tanto, sus valores `ajustado`, `observaciones` y datos de aprobacion no
se pierden durante un recalculo posterior.

Una respuesta exitosa utiliza `200 OK`:

```json
{
  "operation": "replace",
  "destination": "public.pedido_sugerido",
  "forecast_origin": "2026-06-24",
  "status": "completed",
  "deleted_rows": 0,
  "inserted_rows": 64562,
  "calculated_at": "2026-07-18T15:30:45.123Z",
  "duration_ms": 842
}
```

Para consultar los pedidos de una ubicación se utiliza el endpoint paginado:

```bash
curl "http://localhost:8000/api/v1/suggested-orders?location=13&page=1&page_size=50" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

Para limitar los resultados a una fecha de origen del pronostico se puede
enviar el parametro opcional `forecast_origin` en formato `YYYY-MM-DD`:

```bash
curl "http://localhost:8000/api/v1/suggested-orders?location=13&forecast_origin=2026-08-16&page=1&page_size=50" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

`location` es obligatorio. La consulta devuelve solamente registros con
`horizon_day = 1`; este filtro se aplica también al total paginado. `page` inicia
en `1` y `page_size` admite valores de `1` a `200`. Los resultados con
`sugerido > 0` aparecen primero y, dentro de cada grupo, se ordenan por `item`
y `descripcion_tienda`:

```json
{
  "location": 13,
  "page": 1,
  "page_size": 50,
  "total_items": 245,
  "total_pages": 5,
  "items": [
    {
      "item": "ITEM001",
      "forecast_origin": "2026-06-23",
      "horizon_day": 1,
      "target_date": "2026-06-24",
      "location": 13,
      "descripcion_tienda": "Tienda 13",
      "descripcion_item": "Descripción del producto",
      "descripcion_proveedor": "Descripción del proveedor",
      "prediccion": 25.5,
      "ajustado": null,
      "observaciones": null,
      "approved_by": null,
      "approved_at": null,
      "updated_at": null,
      "lead_time_days": 2,
      "review_period_days": 7,
      "uplift_esperado": 0.15,
      "minimum_handling_quantity_units": 5,
      "current_stock_units": 10,
      "on_order_in_transit_units": 3,
      "sugerido": 22,
      "max_qty_vendida": 0,
      "safety_stock": 0,
      "reorder_point": 0,
      "status": "Estimado"
    }
  ]
}
```

## Aprobar pedidos sugeridos en batch

El endpoint autenticado permite aprobar de uno a 500 registros en una sola
transaccion:

```bash
curl -X PATCH http://localhost:8000/api/v1/suggested-orders/batch \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "item": "ITEM001",
        "location": 13,
        "forecast_origin": "2026-08-16",
        "ajustado": 27.5,
        "observaciones": "Ajuste por demanda extraordinaria"
      }
    ]
  }'
```

La API localiza cada registro mediante `item`, `location`, `forecast_origin` y
`horizon_day = 1`. Al actualizar establece `status=Aprobado`, registra el
usuario y la fecha, y guarda el antes y despues en
`public.pedido_sugerido_historial`. Si una llave no existe, ya esta aprobada o
se repite dentro del batch, ninguna modificacion del batch se confirma.

Un registro aprobado no se puede modificar nuevamente. La respuesta incluye
el `batch_id`, conteos y los registros actualizados. `observaciones` es
opcional; puede omitirse o enviarse como `null`.

## Consultar historial de aprobaciones

```bash
curl "http://localhost:8000/api/v1/suggested-orders/history?item=ITEM001&location=13&forecast_origin=2026-08-16&page=1&page_size=50" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

La consulta utiliza siempre `horizon_day = 1` y devuelve los valores anteriores
y nuevos, observaciones, usuario, fecha y `batch_id` de cada modificacion.

## Catálogo de ubicaciones

El catálogo autenticado de ubicaciones se obtiene directamente del maestro de
inventario:

```bash
curl "http://localhost:8000/api/v1/catalogs/locations" \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN"
```

La consulta elimina combinaciones duplicadas, ignora códigos de ubicación nulos
o vacíos, normaliza espacios laterales y ordena por descripción y código:

```json
[
  {
    "location": "13",
    "descripcion_tienda": "Tienda Centro"
  }
]
```

## Migración y propietario

La migración inicial crea todas las tablas en `public` y asigna el propietario
de las tablas de negocio. Las migraciones incrementales conservan los datos:

```sql
ALTER TABLE public.lacteos_ventas_historicas
OWNER TO smartadmin;
ALTER TABLE public.g2_lacteos_promociones_vigentes
OWNER TO smartadmin;
ALTER TABLE public.g2_maestro_inventario_lacteos
OWNER TO smartadmin;
ALTER TABLE public.lacteos_maestro_items
OWNER TO smartadmin;
ALTER TABLE public.lacteos_maestro_tiendas
OWNER TO smartadmin;
ALTER TABLE public.pronostico
OWNER TO smartadmin;
ALTER TABLE public.pedido_sugerido
OWNER TO smartadmin;
ALTER VIEW public.vst_promociones_vigentes
OWNER TO smartadmin;
```

El usuario utilizado para ejecutar Alembic debe ser `smartadmin`, un superusuario
o un rol con permiso para reasignar el propietario.

## Asistente LLM incremental

La primera etapa del Asistente está integrada y deshabilitada por defecto. Esta
entrega incorpora el estado de salud, las diez preguntas de negocio, el
enrutamiento local y las herramientas de consulta de pedidos sugeridos,
pronósticos, ventas históricas, artículos, tiendas, inventario, parámetros,
promociones, ejecuciones, métricas del modelo y explicaciones SHAP globales,
por horizonte y locales.

Configuración:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
ASSISTANT_ENABLED=false
ASSISTANT_REAL_LLM_ENABLED=false
ASSISTANT_ENABLED_TOOLS=consultar_pedidos_sugeridos,consultar_pronosticos,consultar_articulos,consultar_tiendas,consultar_ventas,consultar_inventario,consultar_parametros,consultar_promociones,consultar_ejecuciones,consultar_metricas_modelo,consultar_shap_global,consultar_shap_horizontes,consultar_shap_local
ASSISTANT_MAX_RECORDS=25
ASSISTANT_MAX_TOOL_CALLS=6
ASSISTANT_MAX_MODEL_CALLS=4
ASSISTANT_DEFAULT_FORECAST_ORIGIN=2026-06-24
ASSISTANT_ARTIFACT_DIR=resources/artifacts
ASSISTANT_EXECUTION_DIR=resources/executions
```

`consultar_parametros` utiliza los campos operativos del maestro de inventario,
que es la fuente vigente de tiempos de entrega, periodos de revisión, lotes mínimos
y niveles de servicio en este API. `consultar_ejecuciones` lee exclusivamente el
manifiesto y los archivos de resultados ubicados en `ASSISTANT_EXECUTION_DIR`.
Las métricas y explicaciones leen exclusivamente CSV previamente calculados desde
`ASSISTANT_ARTIFACT_DIR`; estas herramientas no entrenan ni recalculan modelos.

En ejecución local, las rutas anteriores pueden apuntar a directorios Windows.
Docker Compose las reemplaza por `/app/resources/artifacts` y
`/app/resources/executions`, montando las carpetas locales como volúmenes de solo
lectura. Así se pueden actualizar los CSV y archivos de resultados sin reconstruir
la imagen:

```bash
docker compose up -d --build api
docker compose exec api ls -la /app/resources/artifacts
docker compose exec api ls -la /app/resources/executions
```

Puntos de acceso:

```text
GET  /api/v1/assistant-light/health
GET  /api/v1/assistant-light/questions
POST /api/v1/assistant-light/route
POST /api/v1/assistant-light/query
POST /api/v1/assistant/query
```

`health` es público. Las preguntas, el enrutamiento y las consultas requieren
un token OAuth2 Bearer. Para habilitar llamadas reales se deben configurar
explícitamente `ASSISTANT_ENABLED=true`, `ASSISTANT_REAL_LLM_ENABLED=true` y
`OPENAI_API_KEY`. Las pruebas automatizadas usan un cliente simulado y no
consumen tokens.

Ejemplo de consulta:

```bash
curl -X POST http://localhost:8000/api/v1/assistant-light/query \
  -H "Authorization: Bearer REEMPLAZAR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"¿Cuáles son los pedidos sugeridos para la tienda 13?"}'
```

El modelo solo recibe funciones incluidas en la lista cerrada de herramientas
de lectura. No puede aprobar o recalcular pedidos, importar archivos ni ejecutar
SQL libre.

## Archivos grandes

La inserción actual se ejecuta en lotes configurables mediante:

```env
CSV_BATCH_SIZE=1000
```

Para volúmenes de cientos de miles o millones de filas, se recomienda reemplazar
la implementación del repositorio por PostgreSQL `COPY`, sin modificar el router
ni el servicio.
