from hashlib import sha256

import pytest

from cattle_health_app.model_registry import ModelNotFoundError, resolve_detector_model


def test_explicit_detector_path_wins_and_is_fingerprinted(tmp_path):
    weight = tmp_path / "detector.pt"
    weight.write_bytes(b"yolo11-test-weight")

    artifact = resolve_detector_model(explicit_path=weight, project_root=tmp_path)

    assert artifact.path == weight.resolve()
    assert artifact.sha256 == sha256(b"yolo11-test-weight").hexdigest()
    assert artifact.name == "yolo11-detector"


def test_missing_detector_does_not_fall_back_to_generic_coco(tmp_path, monkeypatch):
    monkeypatch.delenv("AGRINEBULA_DETECTOR_MODEL", raising=False)

    with pytest.raises(ModelNotFoundError, match="YOLO11"):
        resolve_detector_model(project_root=tmp_path)
