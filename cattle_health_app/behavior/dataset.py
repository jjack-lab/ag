"""Lazy loading and preprocessing for indexed CVB clips."""

from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Sequence

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, get_worker_info

FRAME_COUNT = 16
KINETICS_MEAN = (0.45, 0.45, 0.45)
KINETICS_STD = (0.225, 0.225, 0.225)
_KINETICS_MEAN_TENSOR = torch.tensor(KINETICS_MEAN, dtype=torch.float32).view(3, 1, 1, 1)
_KINETICS_STD_TENSOR = torch.tensor(KINETICS_STD, dtype=torch.float32).view(3, 1, 1, 1)
EXPECTED_INDEX_FIELDS = (
    "sample_id",
    "video_id",
    "timestamp_seconds",
    "x1",
    "y1",
    "x2",
    "y2",
    "label_id",
    "track_id",
    "group_id",
    "frame_paths",
)


@dataclass(frozen=True)
class ClipSample:
    sample_id: str
    frame_paths: tuple[str, ...]
    bbox: tuple[float, float, float, float]
    label_id: int
    video_id: str
    timestamp_seconds: float
    track_id: int
    group_id: str


class UnreadableClipError(ValueError):
    """A clip frame could not safely be resolved or decoded."""


def expand_normalized_box(bbox: Sequence[float], context: float = 0.15) -> tuple[float, float, float, float]:
    if len(bbox) != 4 or not math.isfinite(context) or context < 0:
        raise ValueError("bbox must have four finite coordinates and context must be nonnegative")
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox coordinates must be numeric") from exc
    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("bbox must be normalized and non-empty")
    dx, dy = (x2 - x1) * context, (y2 - y1) * context
    return max(0.0, x1 - dx), max(0.0, y1 - dy), min(1.0, x2 + dx), min(1.0, y2 + dy)


def _relative_frame_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("frame paths must be non-empty strings")
    # Path.is_absolute on POSIX does not recognize Windows drive paths.
    path = PurePath(value.replace("\\", "/"))
    if Path(value).is_absolute() or path.is_absolute() or (len(value) >= 2 and value[1] == ":") or ".." in path.parts:
        raise ValueError("frame path must remain relative to data_root")
    return value


def load_index(manifest_path: str | Path) -> list[ClipSample]:
    samples = []
    sample_ids: set[str] = set()
    try:
        handle = Path(manifest_path).open(newline="", encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"cannot read manifest: {manifest_path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_INDEX_FIELDS:
            raise ValueError("manifest has an invalid CSV schema")
        for row_number, row in enumerate(reader, 2):
            try:
                if None in row:
                    raise ValueError("schema contains extra row values")
                identifiers = {}
                for field in ("sample_id", "video_id", "group_id"):
                    value = row[field]
                    if value is None or not value.strip():
                        raise ValueError(f"{field} must be non-empty")
                    identifiers[field] = value
                sample_id = identifiers["sample_id"]
                if sample_id in sample_ids:
                    raise ValueError("sample_id must be unique")
                try:
                    timestamp = float(row["timestamp_seconds"])
                except (TypeError, ValueError) as exc:
                    raise ValueError("timestamp_seconds must be numeric") from exc
                if not math.isfinite(timestamp) or timestamp <= 0:
                    raise ValueError("timestamp_seconds must be finite and positive")
                paths_obj = json.loads(row["frame_paths"])
                if not isinstance(paths_obj, list) or len(paths_obj) != FRAME_COUNT:
                    raise ValueError("frame_paths must be a JSON array of exactly 16 paths")
                paths = tuple(_relative_frame_path(v) for v in paths_obj)
                if len(set(paths)) != FRAME_COUNT:
                    raise ValueError("frame paths must be unique")
                bbox = expand_normalized_box(tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2")), 0)
                label_id = int(row["label_id"])
                if not 1 <= label_id <= 12:
                    raise ValueError("label_id is out of range")
                track_id = int(row["track_id"])
                if track_id < 0:
                    raise ValueError("track_id is out of range")
                samples.append(ClipSample(sample_id, paths, bbox, label_id,
                                          identifiers["video_id"], timestamp, track_id,
                                          identifiers["group_id"]))
                sample_ids.add(sample_id)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid manifest row {row_number}: {exc}") from exc
    return samples


def _letterbox(image: np.ndarray, size: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    new_width, new_height = max(1, round(width * scale)), max(1, round(height * scale))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((size, size, 3), dtype=image.dtype)
    left, top = (size - new_width) // 2, (size - new_height) // 2
    canvas[top:top + new_height, left:left + new_width] = resized
    return canvas


def preprocess_clip_bgr(
    frames: Sequence[np.ndarray], size: int = 224, training: bool = False, rng=None
) -> torch.Tensor:
    """Apply the reusable CVB transform to exactly 16 already-cropped BGR images."""
    if len(frames) != FRAME_COUNT or not isinstance(size, int) or size <= 0:
        raise ValueError("transform requires exactly 16 frames and a positive integer size")
    rng = rng if rng is not None else random
    flip = training and rng.random() < 0.5
    brightness = rng.uniform(0.9, 1.1) if training else 1.0
    contrast = rng.uniform(0.9, 1.1) if training else 1.0
    saturation = rng.uniform(0.9, 1.1) if training else 1.0
    output = []
    for frame in frames:
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
                frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0):
            raise ValueError("frames must be non-empty uint8 HxWx3 arrays")
        image = frame
        if flip:
            image = cv2.flip(image, 1)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        if training:
            rgb = (rgb - 0.5) * contrast + 0.5
            gray = rgb.mean(axis=2, keepdims=True)
            rgb = gray + (rgb - gray) * saturation
            rgb = np.clip(rgb * brightness, 0.0, 1.0)
        output.append(_letterbox(rgb, size))
    array = np.stack(output, axis=0)
    tensor = torch.from_numpy(array).permute(3, 0, 1, 2).contiguous()
    return (tensor - _KINETICS_MEAN_TENSOR) / _KINETICS_STD_TENSOR


def evaluation_transform(frames: Sequence[np.ndarray], size: int = 224) -> torch.Tensor:
    return preprocess_clip_bgr(frames, size=size, training=False)


def training_transform(frames: Sequence[np.ndarray], size: int = 224, rng=None) -> torch.Tensor:
    return preprocess_clip_bgr(frames, size=size, training=True, rng=rng)


class CvbClipDataset(Dataset):
    """Dataset returning normalized ``(C,T,H,W)`` clips and zero-based labels."""

    def __init__(self, manifest_path, data_root, training=False, context=0.15, size=224,
                 rng=None, seed=None):
        self.samples = load_index(manifest_path)
        self.data_root = Path(data_root).resolve(strict=True)
        if not self.data_root.is_dir():
            raise ValueError("data_root must be a directory")
        self.training, self.context, self.size = bool(training), context, size
        self._injected_rng, self.seed = rng, seed
        self._worker_rng = None
        self._worker_rng_key = None

    def _augmentation_rng(self):
        worker = get_worker_info()
        if worker is None and self._injected_rng is not None:
            return self._injected_rng
        if worker is None:
            key = ("main", self.seed if self.seed is not None else torch.initial_seed())
            rng_seed = key[1]
        else:
            key = ("worker", worker.id, worker.seed)
            rng_seed = worker.seed
        if self._worker_rng is None or self._worker_rng_key != key:
            self._worker_rng = random.Random(rng_seed)
            self._worker_rng_key = key
        return self._worker_rng

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        sample = self.samples[index]
        bbox = expand_normalized_box(sample.bbox, self.context)
        crops = []
        for relative in sample.frame_paths:
            candidate = self.data_root / relative
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(self.data_root)
            except (OSError, ValueError) as exc:
                raise UnreadableClipError(f"sample {sample.sample_id}: unreadable frame {relative}") from exc
            try:
                image = cv2.imread(str(resolved), cv2.IMREAD_COLOR)
            except Exception as exc:
                raise UnreadableClipError(
                    f"sample {sample.sample_id}: unreadable frame {relative}") from exc
            if image is None or image.ndim != 3 or image.shape[2] != 3 or image.shape[0] < 1 or image.shape[1] < 1:
                raise UnreadableClipError(f"sample {sample.sample_id}: unreadable frame {relative}")
            height, width = image.shape[:2]
            x1 = max(0, min(width - 1, math.floor(bbox[0] * width)))
            y1 = max(0, min(height - 1, math.floor(bbox[1] * height)))
            x2 = max(x1 + 1, min(width, math.ceil(bbox[2] * width)))
            y2 = max(y1 + 1, min(height, math.ceil(bbox[3] * height)))
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                raise UnreadableClipError(f"sample {sample.sample_id}: invalid crop for {relative}")
            crops.append(crop)
        clip = preprocess_clip_bgr(crops, self.size, self.training, self._augmentation_rng())
        return clip, sample.label_id - 1
