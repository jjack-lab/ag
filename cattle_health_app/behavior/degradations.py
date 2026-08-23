"""Reproducible video corruptions for controlled robustness experiments."""

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence, Tuple

import cv2
import numpy as np


DEGRADATION_NAMES = (
    "blur",
    "low_light",
    "occlusion",
    "downsample",
    "frame_drop",
    "compression",
)


class DegradationError(ValueError):
    pass


@dataclass(frozen=True)
class TransformationRecord:
    name: str
    level: int
    parameters: Mapping[str, object]
    seed: int
    input_frame_count: int
    output_frame_count: int
    preserves_shape: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _validated_frames(frames: Sequence[np.ndarray]) -> Tuple[np.ndarray, ...]:
    try:
        rows = tuple(frames)
    except TypeError as exc:
        raise DegradationError("frames must be a non-empty sequence") from exc
    if not rows:
        raise DegradationError("frames must be a non-empty sequence")
    shape = None
    for frame in rows:
        if not isinstance(frame, np.ndarray):
            raise DegradationError("every frame must be a NumPy array")
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise DegradationError("frames must use uint8 HxWx3 model-input format")
        if frame.shape[0] < 2 or frame.shape[1] < 2:
            raise DegradationError("frame dimensions must be at least 2x2")
        if shape is None:
            shape = frame.shape
        elif frame.shape != shape:
            raise DegradationError("all frames must have the same dimensions")
    return rows


def _blur(frames, level):
    sigma = (0.0, 0.8, 1.6, 3.0)[level]
    if level == 0:
        return [frame.copy() for frame in frames], {"sigma": sigma, "kernel_size": 1}
    kernel = int(2 * math.ceil(3 * sigma) + 1)
    output = [
        cv2.GaussianBlur(frame, (kernel, kernel), sigmaX=sigma, sigmaY=sigma)
        for frame in frames
    ]
    return output, {"sigma": sigma, "kernel_size": kernel}


def _low_light(frames, level):
    scale = (1.0, 0.65, 0.40, 0.20)[level]
    output = [
        np.clip(frame.astype(np.float32) * scale, 0, 255).astype(np.uint8)
        for frame in frames
    ]
    return output, {"intensity_scale": scale}


def _occlusion(frames, level, random):
    fraction = (0.0, 0.10, 0.20, 0.35)[level]
    if level == 0:
        return [frame.copy() for frame in frames], {"area_fraction": 0.0}
    height, width = frames[0].shape[:2]
    side_scale = math.sqrt(fraction)
    box_height = max(1, min(height, int(round(height * side_scale))))
    box_width = max(1, min(width, int(round(width * side_scale))))
    top = int(random.randint(0, height - box_height + 1))
    left = int(random.randint(0, width - box_width + 1))
    output = []
    for frame in frames:
        transformed = frame.copy()
        transformed[top : top + box_height, left : left + box_width] = 0
        output.append(transformed)
    return output, {
        "area_fraction": fraction,
        "normalized_box": [
            left / float(width),
            top / float(height),
            (left + box_width) / float(width),
            (top + box_height) / float(height),
        ],
        "fill_value": 0,
    }


def _downsample(frames, level):
    scale = (1.0, 0.75, 0.50, 0.25)[level]
    if level == 0:
        return [frame.copy() for frame in frames], {"linear_scale": scale}
    height, width = frames[0].shape[:2]
    target = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    output = []
    for frame in frames:
        reduced = cv2.resize(frame, target, interpolation=cv2.INTER_AREA)
        output.append(cv2.resize(reduced, (width, height), interpolation=cv2.INTER_LINEAR))
    return output, {
        "linear_scale": scale,
        "intermediate_width": target[0],
        "intermediate_height": target[1],
        "restored_to_input_shape": True,
    }


def _frame_drop(frames, level, random):
    fraction = (0.0, 0.125, 0.25, 0.50)[level]
    if level == 0 or len(frames) == 1:
        return [frame.copy() for frame in frames], {
            "drop_fraction": fraction,
            "dropped_indices": [],
            "replacement": "previous_frame",
        }
    candidates = np.arange(1, len(frames), dtype=np.int64)
    drop_count = min(len(candidates), max(1, int(round(len(frames) * fraction))))
    dropped = sorted(int(value) for value in random.choice(candidates, drop_count, replace=False))
    dropped_set = set(dropped)
    output = []
    last_observed = frames[0]
    for index, frame in enumerate(frames):
        if index in dropped_set:
            output.append(last_observed.copy())
        else:
            output.append(frame.copy())
            last_observed = frame
    return output, {
        "drop_fraction": fraction,
        "dropped_indices": dropped,
        "replacement": "previous_frame",
    }


def _compression(frames, level):
    quality = (100, 70, 45, 20)[level]
    if level == 0:
        return [frame.copy() for frame in frames], {"jpeg_quality": quality}
    output = []
    for frame in frames:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise DegradationError("OpenCV could not encode a compression frame")
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if decoded is None or decoded.shape != frame.shape:
            raise DegradationError("OpenCV violated the compression shape contract")
        output.append(decoded)
    return output, {"codec": "jpeg", "jpeg_quality": quality}


def apply_degradation(
    frames: Sequence[np.ndarray], *, name: str, level: int, seed: int
) -> Tuple[Tuple[np.ndarray, ...], TransformationRecord]:
    """Apply one named severity while preserving model input count and shape.

    ``frame_drop`` represents missing observations by repeating the most recent
    observed frame.  This keeps the model tensor contract fixed while recording
    every simulated missing index in the transformation evidence.
    """

    source = _validated_frames(frames)
    if name not in DEGRADATION_NAMES:
        raise DegradationError("unknown degradation name: {!r}".format(name))
    if isinstance(level, bool) or not isinstance(level, int) or level not in {0, 1, 2, 3}:
        raise DegradationError("level must be an integer from 0 to 3")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise DegradationError("seed must be an integer")
    random = np.random.RandomState(seed)
    if name == "blur":
        transformed, parameters = _blur(source, level)
    elif name == "low_light":
        transformed, parameters = _low_light(source, level)
    elif name == "occlusion":
        transformed, parameters = _occlusion(source, level, random)
    elif name == "downsample":
        transformed, parameters = _downsample(source, level)
    elif name == "frame_drop":
        transformed, parameters = _frame_drop(source, level, random)
    else:
        transformed, parameters = _compression(source, level)

    output = tuple(transformed)
    if len(output) != len(source) or any(
        transformed_frame.shape != source_frame.shape
        or transformed_frame.dtype != source_frame.dtype
        for transformed_frame, source_frame in zip(output, source)
    ):
        raise DegradationError("degradation violated the model input contract")
    return output, TransformationRecord(
        name=name,
        level=level,
        parameters=parameters,
        seed=seed,
        input_frame_count=len(source),
        output_frame_count=len(output),
        preserves_shape=True,
    )
