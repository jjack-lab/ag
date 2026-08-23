import json
from hashlib import sha256

import pytest


def _artifact(checkpoint_bytes=b"checkpoint", **overrides):
    payload = {
        "schema_version": 1,
        "model_version": "cvb-x3d-v1",
        "checkpoint_sha256": sha256(checkpoint_bytes).hexdigest(),
        "validation_manifest_sha256": "b" * 64,
        "validation_selection": {"selected_sample_count": 10},
        "selection_split": "validation",
        "temperature": 0.5,
        "policy": {
            "min_confidence": 0.25,
            "max_normalized_entropy": 0.7,
            "selection_split": "validation",
        },
    }
    payload.update(overrides)
    return payload


def test_load_calibration_requires_matching_checkpoint_and_model_version(tmp_path):
    from cattle_health_app.behavior.calibration import load_behavior_calibration

    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    artifact = tmp_path / "calibration.json"
    artifact.write_text(json.dumps(_artifact()), encoding="utf-8")

    calibration = load_behavior_calibration(
        artifact, checkpoint_path=checkpoint, model_version="cvb-x3d-v1"
    )

    assert calibration.temperature == pytest.approx(0.5)
    assert calibration.min_confidence == pytest.approx(0.25)
    assert calibration.max_normalized_entropy == pytest.approx(0.7)

    checkpoint.write_bytes(b"different")
    with pytest.raises(ValueError, match="checkpoint SHA-256 mismatch"):
        load_behavior_calibration(
            artifact, checkpoint_path=checkpoint, model_version="cvb-x3d-v1"
        )

    checkpoint.write_bytes(b"checkpoint")
    with pytest.raises(ValueError, match="model version mismatch"):
        load_behavior_calibration(
            artifact, checkpoint_path=checkpoint, model_version="another-version"
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature", 0), ("temperature", float("inf"))],
)
def test_load_calibration_rejects_invalid_numeric_values(tmp_path, field, value):
    from cattle_health_app.behavior.calibration import load_behavior_calibration

    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = _artifact()
    payload[field] = value
    artifact = tmp_path / "calibration.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        load_behavior_calibration(
            artifact, checkpoint_path=checkpoint, model_version="cvb-x3d-v1"
        )


def test_media_runtime_uses_matching_neighbor_calibration(tmp_path, monkeypatch):
    import cattle_health_app.media_processor as processor_module

    checkpoint = tmp_path / "cvb_x3d_v2_best.pt"
    checkpoint.write_bytes(b"checkpoint")
    calibration_path = tmp_path / "cvb_x3d_v2_calibration.json"
    calibration_path.write_text(json.dumps(_artifact()), encoding="utf-8")

    class Classifier:
        model_version = "cvb-x3d-v1"
        temperature = 1.0

        def predict(self, clips):
            return [[1.0] + [0.0] * 11 for _ in clips]

    classifier = Classifier()
    monkeypatch.setattr(
        processor_module.TorchBehaviorClassifier,
        "from_checkpoint",
        lambda *args, **kwargs: classifier,
    )
    monkeypatch.setattr(processor_module.torch.cuda, "is_available", lambda: False)

    runtime = processor_module._build_behavior_runtime(checkpoint)

    assert classifier.temperature == pytest.approx(0.5)
    assert runtime.confidence_threshold == pytest.approx(0.25)
    assert runtime.max_normalized_entropy == pytest.approx(0.7)


def test_media_runtime_preserves_legacy_defaults_without_calibration(tmp_path, monkeypatch):
    import cattle_health_app.media_processor as processor_module

    checkpoint = tmp_path / "custom.pt"
    checkpoint.write_bytes(b"checkpoint")

    class Classifier:
        model_version = "custom-v1"
        temperature = 1.0

        def predict(self, clips):
            return [[1.0] + [0.0] * 11 for _ in clips]

    classifier = Classifier()
    monkeypatch.setattr(
        processor_module.TorchBehaviorClassifier,
        "from_checkpoint",
        lambda *args, **kwargs: classifier,
    )
    monkeypatch.setattr(processor_module.torch.cuda, "is_available", lambda: False)

    runtime = processor_module._build_behavior_runtime(checkpoint)

    assert classifier.temperature == pytest.approx(1.0)
    assert runtime.confidence_threshold == pytest.approx(0.45)
    assert runtime.max_normalized_entropy == pytest.approx(1.0)


def test_media_runtime_rejects_missing_explicit_calibration(tmp_path, monkeypatch):
    import cattle_health_app.media_processor as processor_module

    checkpoint = tmp_path / "custom.pt"
    checkpoint.write_bytes(b"checkpoint")
    missing = tmp_path / "missing-calibration.json"
    monkeypatch.setenv("AGRINEBULA_BEHAVIOR_CALIBRATION", str(missing))

    class Classifier:
        model_version = "custom-v1"
        temperature = 1.0

        def predict(self, clips):
            return [[1.0] + [0.0] * 11 for _ in clips]

    monkeypatch.setattr(
        processor_module.TorchBehaviorClassifier,
        "from_checkpoint",
        lambda *args, **kwargs: Classifier(),
    )
    monkeypatch.setattr(processor_module.torch.cuda, "is_available", lambda: False)

    with pytest.raises(FileNotFoundError, match="configured behavior calibration"):
        processor_module._build_behavior_runtime(checkpoint)
