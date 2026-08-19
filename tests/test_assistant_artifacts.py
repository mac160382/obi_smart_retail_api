from pathlib import Path

import pytest

from app.core.config import Settings
from app.modules.assistant.artifacts import (
    ARTIFACT_FILES,
    ArtifactUnavailableError,
    AssistantArtifactStore,
)


def test_artifact_store_reports_available_and_missing_files(tmp_path: Path) -> None:
    metrics = tmp_path / ARTIFACT_FILES["test_metrics"]
    metrics.write_text("evaluation_level,mae\nglobal,1.0\n", encoding="utf-8")
    store = AssistantArtifactStore(Settings.model_construct(assistant_artifact_dir=tmp_path))

    status = {row["role"]: row for row in store.resource_status()}

    assert status["test_metrics"]["available"] is True
    assert status["test_metrics"]["size_bytes"] == metrics.stat().st_size
    assert status["shap_global"]["available"] is False


def test_artifact_store_rejects_missing_required_file(tmp_path: Path) -> None:
    store = AssistantArtifactStore(Settings.model_construct(assistant_artifact_dir=tmp_path))

    with pytest.raises(ArtifactUnavailableError, match="no está disponible"):
        store.rows("shap_global")
