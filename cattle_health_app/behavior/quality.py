"""Deterministic image, track, and temporal quality evidence.

This module deliberately measures observable evidence only.  Acceptance thresholds
and learned quality gates belong to the experiment protocol, where their training
domain and hashes can be audited.
"""

from dataclasses import dataclass
import math
from typing import Iterable, Sequence, Tuple

import numpy as np


class QualityEvidenceError(ValueError):
    """Raised when quality evidence cannot be measured unambiguously."""


@dataclass(frozen=True)
class FrameQuality:
    mean_brightness: float
    dark_ratio: float
    overexposed_ratio: float
    laplacian_variance: float


@dataclass(frozen=True)
class TrackQuality:
    continuity: float
    truncation_ratio: float
    mean_box_area: float
    area_stability: float


@dataclass(frozen=True)
class WindowQuality:
    frame_count: int
    mean_brightness: float
    mean_dark_ratio: float
    mean_overexposed_ratio: float
    mean_laplacian_variance: float
    track_continuity: float
    track_truncation_ratio: float
    track_area_stability: float
    temporal_agreement: float


def _normalized_gray(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim not in {2, 3} or array.shape[0] < 2 or array.shape[1] < 2:
        raise QualityEvidenceError("frame must be a non-empty 2D or 3D image")
    if array.ndim == 3 and array.shape[2] not in {1, 3, 4}:
        raise QualityEvidenceError("frame channels must be grayscale, RGB/BGR, or RGBA")
    if not np.issubdtype(array.dtype, np.number):
        raise QualityEvidenceError("frame must contain numeric pixels")
    values = array.astype(np.float64, copy=False)
    if not np.all(np.isfinite(values)):
        raise QualityEvidenceError("frame contains non-finite pixels")
    if np.issubdtype(array.dtype, np.integer):
        if array.dtype != np.uint8:
            raise QualityEvidenceError("integer frames must use uint8 pixels")
        values = values / 255.0
    elif values.min() < 0.0 or values.max() > 1.0:
        raise QualityEvidenceError("floating-point frames must be normalized to [0, 1]")
    if array.ndim == 3:
        values = values[:, :, :3].mean(axis=2)
    return values


def frame_quality(
    image: np.ndarray,
    *,
    dark_threshold: float = 32.0 / 255.0,
    overexposed_threshold: float = 224.0 / 255.0,
) -> FrameQuality:
    """Measure normalized exposure and spatial-detail evidence for one frame."""

    if not 0.0 <= dark_threshold < overexposed_threshold <= 1.0:
        raise QualityEvidenceError("exposure thresholds must be ordered within [0, 1]")
    gray = _normalized_gray(image)
    laplacian = (
        -4.0 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    laplacian_variance = float(np.var(laplacian)) if laplacian.size else 0.0
    return FrameQuality(
        mean_brightness=float(np.mean(gray)),
        dark_ratio=float(np.mean(gray <= dark_threshold)),
        overexposed_ratio=float(np.mean(gray >= overexposed_threshold)),
        laplacian_variance=laplacian_variance,
    )


def _validated_boxes(boxes: Iterable[Sequence[float]]) -> Tuple[Tuple[float, ...], ...]:
    result = []
    for box in boxes:
        try:
            normalized = tuple(float(value) for value in box)
        except (TypeError, ValueError) as exc:
            raise QualityEvidenceError("boxes must contain four normalized values") from exc
        if len(normalized) != 4 or not all(math.isfinite(value) for value in normalized):
            raise QualityEvidenceError("boxes must contain four normalized values")
        x1, y1, x2, y2 = normalized
        if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
            raise QualityEvidenceError("boxes must be valid and normalized to [0, 1]")
        result.append(normalized)
    if not result:
        raise QualityEvidenceError("at least one box is required")
    return tuple(result)


def track_quality(
    frame_indices: Sequence[int],
    boxes: Iterable[Sequence[float]],
    *,
    boundary_margin: float = 0.01,
) -> TrackQuality:
    """Measure temporal coverage, crop truncation, and box-size stability."""

    indices = tuple(frame_indices)
    normalized_boxes = _validated_boxes(boxes)
    if len(indices) != len(normalized_boxes):
        raise QualityEvidenceError("frame_indices and boxes must have equal length")
    if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in indices):
        raise QualityEvidenceError("frame indices must be integers")
    if any(current <= previous for previous, current in zip(indices, indices[1:])):
        raise QualityEvidenceError("frame indices must be strictly increasing")
    if not math.isfinite(boundary_margin) or not 0.0 <= boundary_margin < 0.5:
        raise QualityEvidenceError("boundary_margin must be within [0, 0.5)")

    expected_count = indices[-1] - indices[0] + 1
    continuity = len(indices) / float(expected_count)
    touches_boundary = [
        x1 <= boundary_margin
        or y1 <= boundary_margin
        or x2 >= 1.0 - boundary_margin
        or y2 >= 1.0 - boundary_margin
        for x1, y1, x2, y2 in normalized_boxes
    ]
    areas = np.asarray(
        [(x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in normalized_boxes],
        dtype=np.float64,
    )
    mean_area = float(np.mean(areas))
    coefficient_of_variation = float(np.std(areas) / mean_area)
    area_stability = 1.0 / (1.0 + coefficient_of_variation)
    return TrackQuality(
        continuity=float(continuity),
        truncation_ratio=float(np.mean(touches_boundary)),
        mean_box_area=mean_area,
        area_stability=area_stability,
    )


def _validated_probabilities(probabilities: Sequence[Sequence[float]]) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
        raise QualityEvidenceError("probabilities require at least two frames and classes")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise QualityEvidenceError("probabilities must be finite and non-negative")
    if not np.allclose(values.sum(axis=1), 1.0, rtol=0.0, atol=1e-6):
        raise QualityEvidenceError("each probability row must sum to one")
    return values


def probability_agreement(probabilities: Sequence[Sequence[float]]) -> float:
    """Return adjacent-distribution agreement in [0, 1]."""

    values = _validated_probabilities(probabilities)
    total_variation = 0.5 * np.abs(values[1:] - values[:-1]).sum(axis=1)
    return float(np.clip(1.0 - np.mean(total_variation), 0.0, 1.0))


def window_quality(
    frames: Sequence[np.ndarray],
    *,
    frame_indices: Sequence[int],
    boxes: Iterable[Sequence[float]],
    probabilities: Sequence[Sequence[float]],
) -> WindowQuality:
    """Aggregate auditable measurements for one model input window."""

    if len(frames) < 2 or len(frames) != len(frame_indices):
        raise QualityEvidenceError("a window needs matching evidence for at least two frames")
    frame_rows = tuple(frame_quality(frame) for frame in frames)
    track = track_quality(frame_indices, boxes)
    values = _validated_probabilities(probabilities)
    if values.shape[0] != len(frames):
        raise QualityEvidenceError("probability rows must match frame count")
    return WindowQuality(
        frame_count=len(frames),
        mean_brightness=float(np.mean([row.mean_brightness for row in frame_rows])),
        mean_dark_ratio=float(np.mean([row.dark_ratio for row in frame_rows])),
        mean_overexposed_ratio=float(
            np.mean([row.overexposed_ratio for row in frame_rows])
        ),
        mean_laplacian_variance=float(
            np.mean([row.laplacian_variance for row in frame_rows])
        ),
        track_continuity=track.continuity,
        track_truncation_ratio=track.truncation_ratio,
        track_area_stability=track.area_stability,
        temporal_agreement=probability_agreement(values),
    )
