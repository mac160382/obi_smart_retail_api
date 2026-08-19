from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.core.config import Settings

ARTIFACT_FILES = {
    "validation_metrics": "phase11_07_random_forest_metrics_cutoff_2026-06-22.csv",
    "test_metrics": "phase11_10_random_forest_test_metrics_cutoff_2026-06-22.csv",
    "shap_sample": "phase12_shap_sample_cutoff_2026-06-22.csv",
    "shap_global": "phase12_shap_global_importance_cutoff_2026-06-22.csv",
    "shap_horizons": "phase12_shap_importance_by_horizon_cutoff_2026-06-22.csv",
    "shap_local": "phase12_shap_local_contributions_cutoff_2026-06-22.csv",
}


class ArtifactUnavailableError(RuntimeError):
    """Raised when a required precomputed analytical artifact is unavailable."""


class AssistantArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.artifact_dir = settings.assistant_artifact_dir.resolve()

    def path(self, role: str) -> Path:
        try:
            filename = ARTIFACT_FILES[role]
        except KeyError as exc:
            raise ValueError(f"Rol de artefacto desconocido: {role}") from exc
        path = (self.artifact_dir / filename).resolve()
        if not path.is_relative_to(self.artifact_dir):
            raise ValueError("La ruta del artefacto está fuera del directorio autorizado.")
        return path

    def require_path(self, role: str) -> Path:
        path = self.path(role)
        if not path.is_file() or path.stat().st_size == 0:
            raise ArtifactUnavailableError(
                f"El artefacto {path.name} no está disponible en {self.artifact_dir}."
            )
        return path

    def rows(self, role: str) -> list[dict[str, str]]:
        path = self.require_path(role)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ArtifactUnavailableError(f"El artefacto {path.name} no contiene encabezados.")
            return [dict(row) for row in reader]

    def resource_status(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for role, filename in ARTIFACT_FILES.items():
            path = self.path(role)
            available = path.is_file() and path.stat().st_size > 0
            result.append(
                {
                    "role": role,
                    "filename": filename,
                    "available": available,
                    "size_bytes": path.stat().st_size if available else None,
                }
            )
        return result


def optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None
