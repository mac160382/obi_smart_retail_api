# Artefactos analíticos

Este directorio contiene métricas y explicaciones SHAP previamente calculadas.
El asistente únicamente lee estos archivos; no entrena ni modifica modelos.

Los dos archivos de métricas se migran desde los resultados existentes. Los
cuatro archivos SHAP deben conservar exactamente los nombres definidos en
`artifact_manifest.json`. Si falta un archivo requerido, la consulta responde
como recurso no disponible en lugar de fabricar una explicación.
