import numpy as np
import pytest

from cattle_health_app.behavior.quality import (
    QualityEvidenceError,
    frame_quality,
    probability_agreement,
    track_quality,
    window_quality,
)


def _checkerboard(size=64, block=4):
    yy, xx = np.indices((size, size))
    mono = (((xx // block) + (yy // block)) % 2 * 255).astype(np.uint8)
    return np.repeat(mono[:, :, None], 3, axis=2)


def test_black_frame_has_high_dark_ratio_and_normalized_brightness():
    quality = frame_quality(np.zeros((32, 32, 3), dtype=np.uint8))

    assert quality.dark_ratio == pytest.approx(1.0)
    assert quality.mean_brightness == pytest.approx(0.0)
    assert quality.overexposed_ratio == pytest.approx(0.0)


def test_blur_score_separates_flat_and_textured_frames():
    flat = np.full((64, 64, 3), 128, np.uint8)
    textured = _checkerboard()

    assert frame_quality(flat).laplacian_variance < frame_quality(
        textured
    ).laplacian_variance


def test_boundary_touching_boxes_have_positive_truncation_evidence():
    complete = track_quality([0, 1, 2], [(0.2, 0.2, 0.8, 0.8)] * 3)
    clipped = track_quality([0, 1, 2], [(0.0, 0.2, 0.8, 0.8)] * 3)

    assert complete.truncation_ratio == pytest.approx(0.0)
    assert clipped.truncation_ratio > 0.0


def test_missing_frame_indices_reduce_track_continuity():
    complete = track_quality([10, 11, 12, 13], [(0.2, 0.2, 0.8, 0.8)] * 4)
    missing = track_quality([10, 11, 13], [(0.2, 0.2, 0.8, 0.8)] * 3)

    assert complete.continuity == pytest.approx(1.0)
    assert missing.continuity < complete.continuity


def test_unstable_probability_sequences_have_lower_agreement():
    stable = np.asarray(
        [[0.90, 0.05, 0.05], [0.85, 0.10, 0.05], [0.88, 0.07, 0.05]]
    )
    unstable = np.asarray(
        [[0.90, 0.05, 0.05], [0.05, 0.90, 0.05], [0.05, 0.05, 0.90]]
    )

    assert probability_agreement(stable) > probability_agreement(unstable)


def test_window_quality_exposes_only_measured_evidence():
    frames = [np.zeros((16, 16, 3), np.uint8), _checkerboard(16, 2)]
    expected_dark_ratio = np.mean([frame_quality(frame).dark_ratio for frame in frames])
    evidence = window_quality(
        frames,
        frame_indices=[0, 1],
        boxes=[(0.1, 0.1, 0.9, 0.9)] * 2,
        probabilities=[[0.8, 0.2], [0.7, 0.3]],
    )

    assert evidence.frame_count == 2
    assert evidence.mean_dark_ratio == pytest.approx(expected_dark_ratio)
    assert evidence.track_continuity == pytest.approx(1.0)
    assert 0.0 <= evidence.temporal_agreement <= 1.0
    assert not hasattr(evidence, "accept")


@pytest.mark.parametrize(
    "call",
    [
        lambda: frame_quality(np.asarray([1, 2, 3])),
        lambda: track_quality([0, 0], [(0.1, 0.1, 0.9, 0.9)] * 2),
        lambda: probability_agreement([[0.4, 0.4]]),
    ],
)
def test_invalid_quality_evidence_is_rejected(call):
    with pytest.raises(QualityEvidenceError):
        call()
