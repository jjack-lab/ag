import numpy as np
import pytest

from cattle_health_app.behavior.external_video_dataset import (
    DecodedVirtualClip,
    ExternalVideoSample,
)
from cattle_health_app.behavior.external_inference import (
    ExternalInferenceError,
    collect_external_predictions,
)


def _sample(sample_id, tier="strict", label="grazing"):
    return ExternalVideoSample(
        sample_id=sample_id,
        source_group_id="group-1",
        source_video_id="1",
        source_video_path="data/external/cbvd5/raw/videos/videos/1.mp4",
        start_second=0,
        end_second=4,
        crop_box=(0.1, 0.1, 0.9, 0.9),
        mapped_label=label,
        mapping_tier=tier,
        source_labels=("foraging",),
        source_sha256="a" * 64,
    )


def test_collect_predictions_preserves_auditable_logits_and_quality(monkeypatch, tmp_path):
    samples = [_sample("a"), _sample("b", "extended", "drinking")]

    def decode(sample, project_root):
        frames = tuple(np.full((16, 16, 3), 100, np.uint8) for _ in range(16))
        label_id = 1 if sample.mapped_label == "grazing" else 7
        return DecodedVirtualClip(sample, frames, tuple(range(16)), label_id)

    monkeypatch.setattr(
        "cattle_health_app.behavior.external_inference.decode_virtual_clip", decode
    )

    def predictor(clips):
        logits = np.zeros((len(clips), 12), dtype=np.float64)
        logits[:, 1] = 2.0
        return logits

    result = collect_external_predictions(
        samples, tmp_path, predictor=predictor, batch_size=2
    )

    assert [row.sample_id for row in result] == ["a", "b"]
    assert len(result[0].logits) == 12
    assert result[0].true_label == 1
    assert result[1].true_label == 7
    assert result[0].quality_features["mean_brightness"] > 0
    assert "track_continuity" in result[0].quality_features


def test_collect_predictions_rejects_invalid_model_shape(monkeypatch, tmp_path):
    sample = _sample("a")
    frames = tuple(np.zeros((16, 16, 3), np.uint8) for _ in range(16))
    monkeypatch.setattr(
        "cattle_health_app.behavior.external_inference.decode_virtual_clip",
        lambda *_: DecodedVirtualClip(sample, frames, tuple(range(16)), 1),
    )

    with pytest.raises(ExternalInferenceError, match="shape"):
        collect_external_predictions(
            [sample], tmp_path, predictor=lambda clips: np.zeros((1, 2)), batch_size=1
        )
