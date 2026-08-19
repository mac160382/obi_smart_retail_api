# Resultados de ejecuciones

`execution_manifest.json` registra las fases que puede consultar el asistente.
Los archivos `.txt` de resultados se colocan en este mismo directorio o en la
ruta externa configurada mediante `ASSISTANT_EXECUTION_DIR`.

Cuando un archivo listado todavía no está disponible, la herramienta devuelve
el registro con `available=false` sin interrumpir las demás consultas.
